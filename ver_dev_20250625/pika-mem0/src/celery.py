from celery import Celery
# Initialize Celery
celery_app = Celery(
    'mem0',
    broker="pyamqp://guest:guest@mem0-rabbitmq:5672//",
    backend="redis://mem0-redis:6379/0"
)
# Import tasks module to ensure tasks are registered
celery_app.autodiscover_tasks(['src.tasks'])
