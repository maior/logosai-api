"""Project management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectShareRequest,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter()


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    current_user: CurrentUser,
    db: DBSession,
    include_archived: bool = Query(False, description="Include archived projects"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    List all projects for current user.

    Returns owned projects (shared projects not yet implemented).
    Requires authentication.
    """
    service = ProjectService(db)
    projects, total = await service.list_by_owner(
        owner_id=current_user.id,
        include_archived=include_archived,
        skip=skip,
        limit=limit,
    )

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
    )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    current_user: CurrentUser,
    db: DBSession,
    project_data: ProjectCreate,
):
    """
    Create a new project.

    Requires authentication.
    """
    service = ProjectService(db)
    project = await service.create(
        owner_id=current_user.id,
        project_data=project_data,
    )
    await db.commit()

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get project details.

    Requires authentication and ownership.
    """
    service = ProjectService(db)
    project = await service.get_by_id_and_owner(
        project_id=project_id,
        owner_id=current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    current_user: CurrentUser,
    db: DBSession,
    project_data: ProjectUpdate,
):
    """
    Update project.

    Requires authentication and ownership.
    """
    service = ProjectService(db)
    project = await service.get_by_id_and_owner(
        project_id=project_id,
        owner_id=current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project = await service.update(project, project_data)
    await db.commit()

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Delete project.

    Requires authentication and ownership.
    """
    service = ProjectService(db)
    project = await service.get_by_id_and_owner(
        project_id=project_id,
        owner_id=current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await service.delete(project)
    await db.commit()


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Archive project.

    Requires authentication and ownership.
    """
    service = ProjectService(db)
    project = await service.get_by_id_and_owner(
        project_id=project_id,
        owner_id=current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project = await service.archive(project)
    await db.commit()

    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/unarchive", response_model=ProjectResponse)
async def unarchive_project(
    project_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Unarchive project.

    Requires authentication and ownership.
    """
    service = ProjectService(db)
    project = await service.get_by_id_and_owner(
        project_id=project_id,
        owner_id=current_user.id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project = await service.unarchive(project)
    await db.commit()

    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/share")
async def share_project(
    project_id: str,
    current_user: CurrentUser,
    share_data: ProjectShareRequest,
):
    """
    Share project with another user.

    Requires authentication and ownership.

    Note: Project sharing is not yet implemented.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Project sharing not implemented yet",
    )
