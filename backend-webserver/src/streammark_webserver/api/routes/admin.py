from fastapi import APIRouter, Depends, HTTPException

from streammark_webserver.api.deps import get_current_admin_user, get_user_repo
from streammark_webserver.api.schemas import AdminUserCreateRequest, UserResponse
from streammark_webserver.security import hash_password
from streammark_webserver.db.repositories import UserRepository

router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    user_repo: UserRepository = Depends(get_user_repo),
) -> list[UserResponse]:
    docs = await user_repo.list()
    return [UserResponse.from_doc(doc) for doc in docs]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: AdminUserCreateRequest,
    user_repo: UserRepository = Depends(get_user_repo),
) -> UserResponse:
    if await user_repo.get_by_email(body.email) is not None:
        raise HTTPException(409, "an account with this email already exists")

    doc = await user_repo.create(body.email, body.name, hash_password(body.password), role=body.role)
    return UserResponse.from_doc(doc)
