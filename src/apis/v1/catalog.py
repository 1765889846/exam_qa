"""GET /colleges · GET /courses — 学院/课程目录。"""

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.dependencies import get_catalog_store, get_current_user
from src.services.storage.catalog_store import CatalogStore

router = APIRouter(tags=["catalog"])


@router.get("/colleges")
async def list_colleges(
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    items = catalog.list_colleges()
    return {
        "code": status.HTTP_200_OK,
        "data": {"items": items, "total": len(items)},
    }


@router.get("/courses")
async def list_courses(
    college_id: str | None = Query(default=None),
    catalog: CatalogStore = Depends(get_catalog_store),
    _user=Depends(get_current_user),
):
    items = catalog.list_courses(college_id=college_id)
    return {
        "code": status.HTTP_200_OK,
        "data": {"items": items, "total": len(items)},
    }
