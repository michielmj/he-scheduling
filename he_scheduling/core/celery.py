from .config import config


try:
    from celery import Celery

    celery = Celery(
        "tasks",
        broker=str(config.celery_broker),
        backend=str(config.celery_result_backend)
    )

except ModuleNotFoundError:
    celery = None
