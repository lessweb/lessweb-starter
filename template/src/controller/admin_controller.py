from typing import Annotated, Optional

import bcrypt
from aiohttp.web import HTTPNotFound
from commondao import Commondao, Paged
from lessweb.annotation import Delete, Get, Post, Put

from shared.jwt_gateway import JwtGateway
from src.entity.admin import (
    Admin,
    AdminChangePasswordInput,
    AdminCreateInput,
    AdminInfoOutput,
    AdminInsert,
    AdminLoginInput,
    AdminLoginOutput,
    AdminUpdate,
    AdminUpdateInput,
)
from src.service.auth_service import AuthRole, CurrentAdmin


async def login_admin(
        login_input: AdminLoginInput,
        /,
        dao: Commondao,
        jwt_gateway: JwtGateway) -> Annotated[AdminLoginOutput, Post('/login/admin')]:
    """
    summary: 管理员登录
    description: 管理员使用用户名和密码登录，验证成功后返回JWT token
    tags:
      - 认证管理
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/AdminLoginInput'
    responses:
      200:
        description: 登录成功，返回JWT token
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AdminLoginOutput'
      400:
        description: 用户名或密码错误，或账号未激活
    """
    # 查询管理员账号
    admin = await dao.select_one(
        'from tbl_admin where username = :username limit 1',
        Admin,
        {'username': login_input.username}
    )

    # 验证账号是否存在
    assert admin, 'Invalid username or password'

    # 验证账号是否激活
    assert admin.isActive, 'Account is not active'

    # 验证密码
    assert bcrypt.checkpw(
        login_input.password.encode('utf-8'),
        admin.passwordHash.encode('utf-8')
    ), 'Invalid username or password'

    # 生成JWT token
    token = jwt_gateway.encrypt_jwt(
        user_id=str(admin.id),
        subject=AuthRole.ADMIN
    )

    # 在Redis中设置登录状态
    await jwt_gateway.login(
        user_id=str(admin.id),
        user_role=AuthRole.ADMIN
    )

    # 返回登录结果
    return AdminLoginOutput(
        token=token,
        adminId=admin.id,
        username=admin.username
    )


async def get_admin_me(current_admin: CurrentAdmin) -> Annotated[AdminInfoOutput, Get('/admin/me')]:
    """
    summary: 获取当前登录管理员信息
    description: 获取当前已登录的管理员的详细信息（不包含密码等敏感信息）
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    responses:
      200:
        description: 成功返回管理员信息
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AdminInfoOutput'
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
    """
    # 通过 CurrentAdmin service 获取当前登录的管理员
    admin = await current_admin.get()

    # 返回管理员信息（不包含 passwordHash）
    return AdminInfoOutput(
        id=admin.id,
        username=admin.username,
        nickname=admin.nickname,
        email=admin.email,
        isActive=admin.isActive,
        createTime=admin.createTime,
        updateTime=admin.updateTime
    )


async def change_password(
        change_password_input: AdminChangePasswordInput,
        /,
        dao: Commondao,
        current_admin: CurrentAdmin,
) -> Annotated[dict, Put('/admin/change-password')]:
    """
    summary: 修改当前登录管理员密码
    description: 校验旧密码正确后，修改当前登录管理员的密码
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/AdminChangePasswordInput'
    responses:
      200:
        description: 修改成功
        content:
          application/json:
            schema:
              type: object
              properties:
                success:
                  type: boolean
      400:
        description: 旧密码错误或参数不合法
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
    """
    admin = await current_admin.get()
    assert bcrypt.checkpw(
        change_password_input.oldPassword.encode('utf-8'),
        admin.passwordHash.encode('utf-8'),
    ), 'Invalid old password'

    assert change_password_input.newPassword, 'newPassword is required'
    assert change_password_input.newPassword != change_password_input.oldPassword, 'newPassword must be different'

    new_password_hash = bcrypt.hashpw(
        change_password_input.newPassword.encode('utf-8'),
        bcrypt.gensalt(),
    ).decode('utf-8')

    updated_count = await dao.execute_mutation(
        'update tbl_admin set passwordHash=:passwordHash where id=:id',
        {'passwordHash': new_password_hash, 'id': admin.id},
    )
    if not updated_count:
        raise RuntimeError('Failed to update password')
    return {'success': True}


async def create_admin(
        create_input: AdminCreateInput,
        /,
        dao: Commondao,
) -> Annotated[AdminInfoOutput, Post('/admin/admins')]:
    """
    summary: 创建管理员
    description: 创建新的管理员账号（检查用户名是否存在、密码至少8位）
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/AdminCreateInput'
    responses:
      200:
        description: 创建成功
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AdminInfoOutput'
      400:
        description: 参数不合法或用户名已存在
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
    """
    assert 1 <= len(create_input.username) <= 100, 'username length must be between 1 and 100'
    assert 1 <= len(create_input.nickname) <= 100, 'nickname length must be between 1 and 100'
    assert len(create_input.password) >= 8, 'Password must be at least 8 characters'
    if create_input.email is not None:
        assert '@' in create_input.email, 'email is invalid'

    username_existing = await dao.select_one(
        'from tbl_admin where username = :username limit 1',
        Admin,
        {'username': create_input.username},
    )
    assert not username_existing, 'Username already exists'

    password_hash = bcrypt.hashpw(
        create_input.password.encode('utf-8'),
        bcrypt.gensalt(),
    ).decode('utf-8')

    inserted = await dao.insert(
        AdminInsert(
            username=create_input.username,
            nickname=create_input.nickname,
            passwordHash=password_hash,
            email=create_input.email,
            isActive=create_input.isActive,
        )
    )
    if not inserted:
        raise RuntimeError('Failed to create admin')
    admin_id = dao.lastrowid()
    admin = await dao.get_by_id_or_fail(Admin, admin_id)

    return AdminInfoOutput(
        id=admin.id,
        username=admin.username,
        nickname=admin.nickname,
        email=admin.email,
        isActive=admin.isActive,
        createTime=admin.createTime,
        updateTime=admin.updateTime,
    )


async def get_admin_by_id(
        dao: Commondao,
        *,
        id: int,
) -> Annotated[AdminInfoOutput, Get('/admin/admins/{id}')]:
    """
    summary: 获取管理员详情
    description: 根据ID获取管理员详情
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: 成功返回管理员详情
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AdminInfoOutput'
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
      404:
        description: 管理员不存在
    """
    admin = await dao.get_by_id(Admin, id)
    if not admin:
        raise HTTPNotFound(text='admin not found')
    return AdminInfoOutput(
        id=admin.id,
        username=admin.username,
        nickname=admin.nickname,
        email=admin.email,
        isActive=admin.isActive,
        createTime=admin.createTime,
        updateTime=admin.updateTime,
    )


async def update_admin_by_id(
        update_input: AdminUpdateInput,
        /,
        dao: Commondao,
        *,
        id: int,
) -> Annotated[AdminInfoOutput, Put('/admin/admins/{id}')]:
    """
    summary: 更新管理员信息
    description: 根据ID更新管理员的username、nickname、email、is_active字段（支持部分更新）
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/AdminUpdateInput'
    responses:
      200:
        description: 更新成功
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AdminInfoOutput'
      400:
        description: 参数不合法或用户名已存在
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
    """
    assert await dao.get_by_id(Admin, id), 'admin not found'

    fields_set = update_input.model_dump(exclude_unset=True, exclude_none=True)
    update_fields: dict = {}
    if 'username' in fields_set:
        assert update_input.username, 'username must not be empty'
        username_existing = await dao.select_one(
            'from tbl_admin where username = :username and id <> :id limit 1',
            Admin,
            {'username': update_input.username, 'id': id},
        )
        assert not username_existing, 'Username already exists'
        update_fields['username'] = update_input.username

    if 'nickname' in fields_set:
        assert update_input.nickname, 'nickname must not be empty'
        update_fields['nickname'] = update_input.nickname

    if 'email' in fields_set:
        assert update_input.email and '@' in update_input.email, 'email is invalid'
        update_fields['email'] = update_input.email

    if 'isActive' in fields_set:
        update_fields['isActive'] = update_input.isActive

    assert update_fields, 'No fields to update'

    updated_count = await dao.update_by_id(AdminUpdate(id=id, **update_fields))
    if not updated_count:
        raise RuntimeError('Failed to update admin')

    admin = await dao.get_by_id_or_fail(Admin, id)
    return AdminInfoOutput(
        id=admin.id,
        username=admin.username,
        nickname=admin.nickname,
        email=admin.email,
        isActive=admin.isActive,
        createTime=admin.createTime,
        updateTime=admin.updateTime,
    )


async def get_admins(
        dao: Commondao,
        *,
        username: Optional[str] = None,
        nickname: Optional[str] = None,
        email: Optional[str] = None,
        isActive: Optional[bool] = None,
        offset: int = 0,
        size: int = 10,
) -> Annotated[Paged[AdminInfoOutput], Get('/admin/admins')]:
    """
    summary: 分页查询管理员列表
    description: 获取管理员列表，支持分页参数和筛选条件（username、nickname、email、isActive、offset、size）
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    parameters:
      - name: username
        in: query
        required: false
        schema:
          type: string
        description: 用户名筛选（模糊匹配）
      - name: nickname
        in: query
        required: false
        schema:
          type: string
        description: 昵称筛选（模糊匹配）
      - name: email
        in: query
        required: false
        schema:
          type: string
        description: 邮箱筛选（模糊匹配）
      - name: isActive
        in: query
        required: false
        schema:
          type: boolean
        description: 是否激活筛选
      - name: offset
        in: query
        required: false
        schema:
          type: integer
          default: 0
        description: 偏移量，默认为0
      - name: size
        in: query
        required: false
        schema:
          type: integer
          default: 10
        description: 每页数量，默认为10
    responses:
      200:
        description: 成功返回管理员列表
        content:
          application/json:
            schema:
              type: object
              properties:
                items:
                  type: array
                  items:
                    $ref: '#/components/schemas/AdminInfoOutput'
                offset:
                  type: integer
                size:
                  type: integer
                total:
                  type: integer
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
    """
    # 构建查询条件
    where_clauses = []
    params: dict = {}

    if username is not None:
        where_clauses.append('username LIKE :username')
        params['username'] = f'%{username}%'

    if nickname is not None:
        where_clauses.append('nickname LIKE :nickname')
        params['nickname'] = f'%{nickname}%'

    if email is not None:
        where_clauses.append('email LIKE :email')
        params['email'] = f'%{email}%'

    if isActive is not None:
        where_clauses.append('isActive = :isActive')
        params['isActive'] = isActive

    # 构建WHERE子句
    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'

    # 使用select_paged进行分页查询
    return await dao.select_paged(
        f'from tbl_admin where {where_sql} order by id desc',
        AdminInfoOutput,
        params,
        size=size,
        offset=offset
    )


async def delete_admin_by_id(
        dao: Commondao,
        *,
        id: int,
) -> Annotated[dict, Delete('/admin/admins/{id}')]:
    """
    summary: 删除管理员
    description: 根据ID删除管理员
    tags:
      - 管理员管理
    security:
      - bearerAuth: []
    parameters:
      - name: id
        in: path
        required: true
        schema:
          type: integer
    responses:
      200:
        description: 删除成功
        content:
          application/json:
            schema:
              type: object
              properties:
                success:
                  type: boolean
      401:
        description: 未登录或token无效
      403:
        description: 无权限访问（非管理员角色）
    """
    await dao.delete_by_id(Admin, id)
    return {'success': True}
