# FinMind Local Kubernetes Development Workflow (Tilt)
allow_k8s_contexts(['minikube', 'docker-desktop', 'kind-kind', 'kind-finmind', 'k3d-finmind', 'default'])

# Build backend container with live reload
docker_build(
    'ghcr.io/rohitdash08/finmind-backend',
    './packages/backend',
    dockerfile='./packages/backend/Dockerfile',
    live_update=[
        sync('./packages/backend/app', '/app/app'),
        sync('./packages/backend/wsgi.py', '/app/wsgi.py'),
        run('pip install -r /app/requirements.txt', trigger=['./packages/backend/requirements.txt']),
    ],
)

# Build frontend container with live update
docker_build(
    'ghcr.io/rohitdash08/finmind-frontend',
    './app',
    dockerfile='./app/Dockerfile',
    live_update=[
        sync('./app/src', '/app/src'),
        sync('./app/public', '/app/public'),
    ],
)

# Render Helm chart
k8s_yaml(helm(
    './deploy/helm/finmind',
    name='finmind',
    namespace='finmind',
    values=['./deploy/helm/finmind/values.yaml'],
))

# Configure resource ordering and local port-forwards
k8s_resource('finmind-postgres', port_forwards='5432:5432', labels=['database'])
k8s_resource('finmind-redis', port_forwards='6379:6379', labels=['cache'])
k8s_resource(
    'finmind-backend',
    port_forwards='8000:8000',
    resource_deps=['finmind-postgres', 'finmind-redis'],
    labels=['backend'],
)
k8s_resource(
    'finmind-frontend',
    port_forwards='5173:80',
    resource_deps=['finmind-backend'],
    labels=['frontend'],
)
