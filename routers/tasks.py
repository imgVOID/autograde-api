from fastapi import status, File, UploadFile, APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.requests import Request
from fastapi.encoders import jsonable_encoder
from routers import limiter
from schemas.tasks import Task, TaskUpdate, TaskCreate
from schemas.errors import NotFoundTheme, NotFoundTask, EmptyRequest
from utilities.file_scripts import FileUtils

router_tasks = APIRouter(
    redirect_slashes=False,
    prefix="/api/tasks",
    tags=["tasks"],
)


@router_tasks.get(
    "/{theme_id}/{task_id}", status_code=200, summary="Read task by ID",
    response_model=Task, responses={404: {"model": NotFoundTask}},
)
async def read_task(theme_id: int, task_id: int) -> Task or JSONResponse:
    """The `read task` CRUD endpoint."""
    try:
        # Get task info, inputs and outputs.
        description = await FileUtils.open_file('task_info', theme_id, task_id)
        inputs = await FileUtils.open_file_values('task_input', theme_id, task_id)
        outputs = await FileUtils.open_file_values('task_output', theme_id, task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=NotFoundTask().error)
    except IndexError:
        raise HTTPException(status_code=404, detail=NotFoundTheme().error)
    else:
        return Task(**description, input=list(inputs), output=list(outputs))


@router_tasks.post(
    "/{theme_id}", status_code=201, summary="Create new task",
    response_model=Task, responses={404: {"model": NotFoundTheme}}
)
@limiter.limit("10/minute")
async def create_task(
        request: Request, response: Response, theme_id: int,
        task: TaskCreate or UploadFile, code: UploadFile = File(...)
) -> Task or JSONResponse:
    """The `create task` CRUD endpoint."""
    # If this is a test mode, the actual data will be protected from changes.
    try:
        themes_json = await FileUtils.open_file('theme_index', theme_id=theme_id)
    except IndexError:
        raise HTTPException(status_code=404, detail=NotFoundTheme().error)
    if isinstance(task, UploadFile):
        task = TaskCreate(**jsonable_encoder(task))
    # Get ID
    task_id = themes_json[theme_id].get("count") + 1
    # Create new task
    task = Task(
        id=task_id, theme_id=theme_id, **task.dict()
    )
    # New task's info dictionary
    task_description = {key: value for key, value in task
                        if key in ("id", "theme_id", "title", "description")}
    # Save task info
    await FileUtils.save_file(
        'task_info', content=task_description, theme_id=theme_id, task_id=task.id
    )
    # Save task's input values
    await FileUtils.save_file_values(
        "task_input", content=task.input, theme_id=theme_id, task_id=task.id
    )
    # Save task code's output values
    await FileUtils.save_file_values(
        "task_output", content=task.output, theme_id=theme_id, task_id=task.id
    )
    # Save task's code
    await FileUtils.save_file(
        "task_code", content=await code.read(), theme_id=theme_id, task_id=task.id
    )
    # Update the theme tasks count
    themes_json[theme_id]["count"] = task_id
    await FileUtils.save_file('theme_index', content=themes_json)
    return task


@router_tasks.put(
    "/{theme_id}/{task_id}", status_code=200, summary="Update task by ID",
    response_model=TaskUpdate, response_model_exclude_none=True,
    responses={404: {"model": NotFoundTask}}
)
@limiter.limit("10/minute")
async def update_task(
        request: Request, response: Response, theme_id: int, task_id: int,
        task: TaskUpdate, code: UploadFile = File(None)
) -> Task or JSONResponse:
    """The `update task` CRUD endpoint.\n
    You can update description, code, inputs and outputs,
    one at a time, or all at once.\n
    Please uncheck "Send empty value" in Swagger UI!
    """
    if isinstance(task, UploadFile):
        task = TaskUpdate(**jsonable_encoder(task))
    task.theme_id = theme_id
    task.id = task_id
    task_update = jsonable_encoder(task)
    new_task_info = (
        task_update.get("title"), task_update.get("description"),
        task_update.get("input"), task_update.get("output"),
        await code.read()
    )
    # Check if there was an empty request
    if not any(new_task_info):
        raise HTTPException(status_code=422, detail=EmptyRequest().error)
    # Update task's description
    if any(new_task_info[0:2]):
        try:
            # Get task info
            task_info = await FileUtils.open_file(
                "task_info", theme_id=theme_id, task_id=task_id
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=NotFoundTask().error)
        except IndexError:
            raise HTTPException(status_code=404, detail=NotFoundTheme().error)
        else:
            task_info["title"] = new_task_info[0] if new_task_info[0] else task_info["title"]
            task_info["description"] = new_task_info[1] if new_task_info[1] else task_info["description"]
            # Save task info
            await FileUtils.save_file(
                "task_info", content=task_info, theme_id=task.theme_id, task_id=task.id
            )
    # Update task's input values
    if new_task_info[2]:
        try:
            await FileUtils.save_file_values(
                "task_input", content=task_update.get("input"),
                theme_id=theme_id, task_id=task.id,
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=NotFoundTask().error)
    # Update task answer's output values
    if new_task_info[3]:
        try:
            await FileUtils.save_file_values(
                "task_output", content=task_update.get("output"),
                theme_id=theme_id, task_id=task.id,
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=NotFoundTask().error)
    # Update task's code file
    if new_task_info[4]:
        try:
            await FileUtils.save_file(
                "task_code", content=new_task_info[4], theme_id=theme_id, task_id=task.id
            )
        except IndexError:
            raise HTTPException(status_code=404, detail=NotFoundTheme().error)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=NotFoundTask().error)
    return Task(task_id=task.id, **task_update)


@router_tasks.delete(
    "/{theme_id}/{task_id}", status_code=204, summary="Delete task by ID",
    responses={404: {"model": NotFoundTask}}
)
@limiter.limit("10/minute")
async def delete_task(
        request: Request, response: Response, task_id: int, theme_id: int
) -> Response or JSONResponse:
    """The `delete task` CRUD endpoint."""
    files = ("task_info", "task_input", "task_output", "task_code")
    for title in files:
        try:
            await FileUtils.remove_file(title, theme_id=theme_id, task_id=task_id)
        except IndexError:
            raise HTTPException(status_code=404, detail=NotFoundTheme().error)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=NotFoundTask().error)
    # Open themes info
    themes = await FileUtils.open_file('theme_index')
    # Update the theme tasks count
    themes[theme_id]["count"] -= 1
    await FileUtils.save_file('theme_index', content=themes, theme_id=theme_id, task_id=task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
