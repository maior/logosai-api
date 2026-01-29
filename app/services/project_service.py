"""Project service for database operations."""

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    """Service for project-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by ID."""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_owner(
        self,
        project_id: str,
        owner_id: str,
    ) -> Optional[Project]:
        """Get project by ID and owner."""
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_id: str,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Project], int]:
        """List projects by owner."""
        query = select(Project).where(Project.owner_id == owner_id)

        if not include_archived:
            query = query.where(Project.is_archived == False)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(Project.updated_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        projects = list(result.scalars().all())

        return projects, total

    async def create(
        self,
        owner_id: str,
        project_data: ProjectCreate,
    ) -> Project:
        """Create a new project."""
        project = Project(
            owner_id=owner_id,
            name=project_data.name,
            description=project_data.description,
            color=project_data.color,
            icon=project_data.icon,
        )
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def update(
        self,
        project: Project,
        project_data: ProjectUpdate,
    ) -> Project:
        """Update a project."""
        update_data = project_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(project, field, value)

        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        """Delete a project."""
        await self.db.delete(project)
        await self.db.flush()

    async def archive(self, project: Project) -> Project:
        """Archive a project."""
        project.is_archived = True
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def unarchive(self, project: Project) -> Project:
        """Unarchive a project."""
        project.is_archived = False
        await self.db.flush()
        await self.db.refresh(project)
        return project
