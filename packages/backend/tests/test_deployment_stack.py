from datetime import date, timedelta
import json
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_health_and_readiness_probes_verify_db_and_redis(client, monkeypatch):
    r_live = client.get("/health")
    assert r_live.status_code == 200
    assert r_live.get_json()["status"] == "ok"

    r_ready = client.get("/health/ready")
    assert r_ready.status_code == 200
    body = r_ready.get_json()
    assert body["status"] == "ok"
    assert body["components"]["database"] == "ok"
    assert body["components"]["redis"] == "ok"

    # Simulate Redis outage -> 503 degraded
    from app.extensions import redis_client

    monkeypatch.setattr(redis_client, "ping", lambda: (_ for _ in ()).throw(RuntimeError("redis down")))
    r_deg = client.get("/health/ready")
    assert r_deg.status_code == 503
    assert r_deg.get_json()["components"]["redis"] == "error"


def test_helm_chart_and_templates_exist_and_configure_hpa_ingress_pdb():
    chart_dir = REPO_ROOT / "deploy" / "helm" / "finmind"
    chart_meta = yaml.safe_load((chart_dir / "Chart.yaml").read_text(encoding="utf-8"))
    values = yaml.safe_load((chart_dir / "values.yaml").read_text(encoding="utf-8"))

    assert chart_meta["name"] == "finmind"
    assert values["backend"]["autoscaling"]["enabled"] is True
    assert values["ingress"]["tls"]["enabled"] is True
    assert values["backend"]["pdb"]["enabled"] is True

    expected_templates = [
        "namespace.yaml",
        "configmap.yaml",
        "secrets.yaml",
        "postgres.yaml",
        "redis.yaml",
        "backend.yaml",
        "frontend.yaml",
        "ingress.yaml",
        "hpa.yaml",
        "pdb.yaml",
    ]
    for tpl in expected_templates:
        tpl_path = chart_dir / "templates" / tpl
        assert tpl_path.exists(), f"Missing Helm template: {tpl}"

    backend_tpl = (chart_dir / "templates" / "backend.yaml").read_text(encoding="utf-8")
    assert "/health/ready" in backend_tpl
    assert "livenessProbe" in backend_tpl


def test_tiltfile_and_docker_compose_prod_configurations():
    tilt_src = (REPO_ROOT / "Tiltfile").read_text(encoding="utf-8")
    assert "docker_build" in tilt_src
    assert "live_update" in tilt_src
    assert "deploy/helm/finmind" in tilt_src

    compose_prod = yaml.safe_load(
        (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )
    services = compose_prod["services"]
    assert {"postgres", "redis", "backend", "frontend"}.issubset(set(services.keys()))
    assert services["backend"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["backend"]["depends_on"]["redis"]["condition"] == "service_healthy"


def test_all_twelve_mandatory_cloud_platform_manifests_are_valid():
    # 1. Railway
    assert (REPO_ROOT / "railway.toml").exists()
    rw_json = json.loads((REPO_ROOT / "deploy" / "platforms" / "railway.json").read_text(encoding="utf-8"))
    assert rw_json["deploy"]["healthcheckPath"] == "/health"

    # 2. Heroku
    heroku_yml = yaml.safe_load((REPO_ROOT / "heroku.yml").read_text(encoding="utf-8"))
    assert "web" in heroku_yml["build"]["docker"]
    assert (REPO_ROOT / "Procfile").exists()
    app_json = json.loads((REPO_ROOT / "app.json").read_text(encoding="utf-8"))
    assert app_json["stack"] == "container"

    # 3 & 4. DigitalOcean App Platform + Droplet
    do_app = yaml.safe_load((REPO_ROOT / ".do" / "app.yaml").read_text(encoding="utf-8"))
    assert do_app["name"] == "finmind"
    assert (REPO_ROOT / "deploy" / "platforms" / "do-droplet-setup.sh").exists()

    # 5. Render
    render_yml = yaml.safe_load((REPO_ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert len(render_yml["services"]) >= 3

    # 6. Fly.io
    fly_toml = (REPO_ROOT / "fly.toml").read_text(encoding="utf-8")
    assert 'path = "/health"' in fly_toml
    assert (REPO_ROOT / "deploy" / "platforms" / "fly.frontend.toml").exists()

    # 7. AWS (ECS Fargate, App Runner, EC2)
    ecs_def = json.loads(
        (REPO_ROOT / "deploy" / "platforms" / "aws" / "ecs-task-definition.json").read_text(encoding="utf-8")
    )
    assert "FARGATE" in ecs_def["requiresCompatibilities"]
    assert (REPO_ROOT / "deploy" / "platforms" / "aws" / "apprunner.yaml").exists()
    assert (REPO_ROOT / "deploy" / "platforms" / "aws" / "ec2-deploy.sh").exists()

    # 8. GCP Cloud Run
    crun = yaml.safe_load(
        (REPO_ROOT / "deploy" / "platforms" / "gcp" / "cloudrun-service.yaml").read_text(encoding="utf-8")
    )
    assert crun["kind"] == "Service"
    assert (REPO_ROOT / "deploy" / "platforms" / "gcp" / "cloudbuild.yaml").exists()

    # 9. Azure Container Apps
    az = yaml.safe_load(
        (REPO_ROOT / "deploy" / "platforms" / "azure" / "containerapp.yaml").read_text(encoding="utf-8")
    )
    assert az["type"] == "Microsoft.App/containerApps"

    # 10 & 11. Netlify & Vercel
    assert (REPO_ROOT / "netlify.toml").exists()
    vercel_cfg = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert vercel_cfg["framework"] == "vite"

    # 12. Dispatcher & Verification scripts
    assert (REPO_ROOT / "scripts" / "deploy.sh").exists()
    assert (REPO_ROOT / "scripts" / "verify-deployment.py").exists()
    assert (REPO_ROOT / "DEPLOY.md").exists()


def test_runtime_acceptance_criteria_across_all_core_modules(client, auth_header):
    # Verify Categories
    r_cat = client.post("/categories", json={"name": "Operations"}, headers=auth_header)
    assert r_cat.status_code == 201
    cat_id = r_cat.get_json()["id"]

    # Verify Expenses
    r_exp = client.post(
        "/expenses",
        json={"amount": 150.0, "description": "Cloud hosting", "category_id": cat_id},
        headers=auth_header,
    )
    assert r_exp.status_code == 201

    # Verify Bills
    due = (date.today() + timedelta(days=5)).isoformat()
    r_bill = client.post(
        "/bills",
        json={"name": "Cluster Node", "amount": 500.0, "next_due_date": due, "cadence": "MONTHLY"},
        headers=auth_header,
    )
    assert r_bill.status_code == 201
    bill_id = r_bill.get_json()["id"]

    # Verify Reminders
    r_rem = client.post(
        "/reminders",
        json={
            "bill_id": bill_id,
            "message": "Cluster Node payment due soon",
            "send_at": f"{due}T09:00:00",
            "channel": "email",
        },
        headers=auth_header,
    )
    assert r_rem.status_code == 201

    # Verify Dashboard
    r_dash = client.get("/dashboard/summary", headers=auth_header)
    assert r_dash.status_code == 200

    # Verify Insights
    r_ins = client.get("/insights/budget-suggestion", headers=auth_header)
    assert r_ins.status_code == 200
