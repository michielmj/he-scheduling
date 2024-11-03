from fastapi import APIRouter, HTTPException
from celery import states
from celery.result import AsyncResult
import uuid
from he_scheduling.models.master_planning import MPModelRequest, MPJobStatusResponse
from he_scheduling.core.celery import celery
from he_scheduling.tasks.master_planning import solve_scheduling_problem

router = APIRouter(prefix='/api/v2/master-planning')


# Endpoint to submit a new problem
@router.post("/submit_problem/", response_model=MPJobStatusResponse)
async def submit_problem(problem: MPModelRequest):
    # Generate a unique job ID for tracking
    job_id = str(uuid.uuid4())
    # Submit the task to Celery
    task = solve_scheduling_problem.apply_async(args=[problem], task_id=job_id)
    return {"job_id": task.id, "status": "submitted"}


# Endpoint to retrieve job status and result
@router.get("/job_status/{job_id}", response_model=MPJobStatusResponse)
async def job_status(job_id: str):
    task_result = AsyncResult(job_id, app=celery)
    if task_result.state == states.PENDING:
        return {"job_id": job_id, "status": "pending"}
    elif task_result.state == states.STARTED:
        return {"job_id": job_id, "status": "in progress"}
    elif task_result.state == states.SUCCESS:
        return {"job_id": job_id, "status": "completed", "result": task_result.result}
    elif task_result.state == states.FAILURE:
        return {"job_id": job_id, "status": "failed", "result": str(task_result.result)}
    else:
        return {"job_id": job_id, "status": task_result.state}


# Endpoint to cancel a job
@router.delete("/cancel_job/{job_id}")
async def cancel_job(job_id: str):
    task_result = AsyncResult(job_id, app=celery)
    if task_result.state in [states.PENDING, states.STARTED]:
        task_result.revoke(terminate=True)
        return {"job_id": job_id, "status": "canceled"}
    elif task_result.state == states.SUCCESS:
        raise HTTPException(status_code=400, detail="Job already completed and cannot be canceled.")
    else:
        return {"job_id": job_id, "status": task_result.state}
