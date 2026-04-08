from datetime import datetime
from typing import Annotated, Optional

from commondao.annotation import TableId
from pydantic import BaseModel


class Admin(BaseModel):
    """
    管理员实体 - 用于查询
    """
    id: Annotated[int, TableId('tbl_admin')]
    username: str
    nickname: str
    passwordHash: str
    email: Optional[str] = None
    isActive: bool
    createTime: datetime
    updateTime: datetime


class AdminInsert(BaseModel):
    """
    管理员实体 - 用于插入
    """
    id: Annotated[Optional[int], TableId('tbl_admin')] = None  # Auto-increment
    username: str
    nickname: str
    passwordHash: str
    email: Optional[str] = None
    isActive: bool = True


class AdminUpdate(BaseModel):
    """
    管理员实体 - 用于更新
    """
    id: Annotated[Optional[int], TableId('tbl_admin')] = None
    username: Optional[str] = None
    nickname: Optional[str] = None
    passwordHash: Optional[str] = None
    email: Optional[str] = None
    isActive: Optional[bool] = None


# DTO Models

class AdminLoginInput(BaseModel):
    """管理员登录请求DTO"""
    username: str
    password: str


class AdminLoginOutput(BaseModel):
    """管理员登录响应DTO"""
    token: str
    adminId: int
    username: str


class AdminInfoOutput(BaseModel):
    """管理员信息输出DTO（不包含敏感信息）"""
    id: int
    username: str
    nickname: str
    email: Optional[str] = None
    isActive: bool
    createTime: datetime
    updateTime: datetime


class AdminChangePasswordInput(BaseModel):
    """修改当前管理员密码请求DTO"""
    oldPassword: str
    newPassword: str


class AdminCreateInput(BaseModel):
    """创建管理员请求DTO"""
    username: str
    nickname: str
    password: str
    email: Optional[str] = None
    isActive: bool = True


class AdminUpdateInput(BaseModel):
    """更新管理员请求DTO（部分字段可选）"""
    username: Optional[str] = None
    nickname: Optional[str] = None
    email: Optional[str] = None
    isActive: Optional[bool] = None
