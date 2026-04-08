import time

import bcrypt
import pytest
from commondao import connect
from lessweb import Bridge
from lessweb.ioc import APP_CONFIG_KEY
from lessweb.utils import absolute_ref

from main import load_environ
from shared.error_middleware import error_middleware
from shared.jwt_gateway import JwtGateway, JwtGatewayMiddleware
from shared.lessweb_commondao import MysqlConn, commondao_bean
from shared.redis_plugin import redis_bean


class TestAdminController:
    """Admin controller e2e tests"""

    @pytest.fixture
    async def app_client(self, aiohttp_client):
        """Create test app with real database connection"""
        # Create Bridge instance with real config
        load_environ()
        bridge = Bridge('config')
        bridge.beans(commondao_bean, redis_bean)
        # Register middlewares explicitly (not via scan)
        # Order matters: error_middleware should be first to catch exceptions
        bridge.middlewares(error_middleware, JwtGatewayMiddleware, MysqlConn)
        # Scan 'src' will auto-load JwtGateway from admin_controller.py
        bridge.scan('src')
        bridge.ready()

        client = await aiohttp_client(bridge.app)
        return client

    @pytest.fixture
    async def test_admin_cleanup(self, app_client):
        """Setup and cleanup test admin data"""
        client = app_client
        timestamp = str(int(time.time() * 1000))

        # Track created test admin usernames for cleanup
        created_usernames = []

        def track_creation(username: str):
            """Helper to track test admin for cleanup"""
            if username not in created_usernames:
                created_usernames.append(username)

        # Get database config
        mysql_config = client.app[APP_CONFIG_KEY]['mysql'].copy()
        mysql_config['port'] = int(mysql_config['port'])

        # Cleanup before tests
        async with connect(**mysql_config) as db:
            await db.execute_mutation(
                'DELETE FROM tbl_admin WHERE username LIKE :pattern',
                {'pattern': 'test_admin_%'}
            )

        yield {
            'timestamp': timestamp,
            'client': client,
            'track_creation': track_creation,
            'created_usernames': created_usernames,
            'mysql_config': mysql_config
        }

        # Cleanup after tests
        async with connect(**mysql_config) as db:
            for username in created_usernames:
                await db.execute_mutation(
                    'DELETE FROM tbl_admin WHERE username = :username',
                    {'username': username}
                )

    @pytest.fixture
    async def create_test_admin(self, test_admin_cleanup):
        """Create a test admin user in database"""
        test_data = test_admin_cleanup
        timestamp = test_data['timestamp']
        username = f"test_admin_{timestamp}"
        nickname = f"nick_{timestamp}"
        password = "test_password_123"

        # Hash password using bcrypt
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Insert test admin into database
        mysql_config = test_data['mysql_config']
        async with connect(**mysql_config) as db:
            # Use execute_mutation with explicit SQL to insert admin
            await db.execute_mutation(
                '''INSERT INTO tbl_admin (username, nickname, passwordHash, email, isActive)
                   VALUES (:username, :nickname, :passwordHash, :email, :isActive)''',
                {
                    'username': username,
                    'nickname': nickname,
                    'passwordHash': password_hash,
                    'email': f"{username}@example.com",
                    'isActive': 1  # 1 for active, 0 for inactive
                }
            )
            # Commit the transaction to ensure data is persisted
            await db.commit()
            # Get the last inserted ID using lastrowid method
            admin_id = db.lastrowid()

        test_data['track_creation'](username)

        return {
            **test_data,
            'username': username,
            'nickname': nickname,
            'password': password,
            'admin_id': admin_id
        }

    @pytest.mark.asyncio
    async def test_login_admin_success(self, create_test_admin):
        """Test admin login with correct credentials"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        password = test_data['password']

        # Login with correct credentials
        resp = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })

        assert resp.status == 200
        data = await resp.json()

        # Verify response structure
        assert 'token' in data
        assert 'adminId' in data
        assert 'username' in data

        # Verify response content
        assert data['username'] == username
        assert data['adminId'] == test_data['admin_id']
        assert isinstance(data['token'], str)
        assert len(data['token']) > 0

    @pytest.mark.asyncio
    async def test_login_admin_invalid_username(self, test_admin_cleanup):
        """Test admin login with invalid username"""
        client = test_admin_cleanup['client']

        # Login with non-existent username
        resp = await client.post('/login/admin', json={
            'username': 'nonexistent_admin',
            'password': 'any_password'
        })

        assert resp.status == 400
        resp_text = await resp.text()
        assert 'Invalid username or password' in resp_text

    @pytest.mark.asyncio
    async def test_login_admin_invalid_password(self, create_test_admin):
        """Test admin login with wrong password"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']

        # Login with wrong password
        resp = await client.post('/login/admin', json={
            'username': username,
            'password': 'wrong_password'
        })

        assert resp.status == 400
        resp_text = await resp.text()
        assert 'Invalid username or password' in resp_text

    @pytest.mark.asyncio
    async def test_login_admin_inactive_account(self, test_admin_cleanup):
        """Test admin login with inactive account"""
        test_data = test_admin_cleanup
        client = test_data['client']
        timestamp = test_data['timestamp']
        username = f"test_admin_inactive_{timestamp}"
        nickname = f"nick_inactive_{timestamp}"
        password = "test_password_123"

        # Create inactive admin
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        mysql_config = test_data['mysql_config']

        async with connect(**mysql_config) as db:
            await db.execute_mutation(
                '''INSERT INTO tbl_admin (username, nickname, passwordHash, email, isActive)
                   VALUES (:username, :nickname, :passwordHash, :email, :isActive)''',
                {
                    'username': username,
                    'nickname': nickname,
                    'passwordHash': password_hash,
                    'email': f"{username}@example.com",
                    'isActive': 0  # 0 for inactive, 1 for active
                }
            )
            # Commit the transaction to ensure data is persisted
            await db.commit()

        test_data['track_creation'](username)

        # Try to login with inactive account
        resp = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })

        assert resp.status == 400
        resp_text = await resp.text()
        assert 'Account is not active' in resp_text

    @pytest.mark.asyncio
    async def test_get_admin_me_success(self, create_test_admin):
        """Test getting current admin info with valid token"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        nickname = test_data['nickname']
        password = test_data['password']

        # First login to get token
        login_resp = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })
        assert login_resp.status == 200
        login_data = await login_resp.json()
        token = login_data['token']

        # Get current admin info
        resp = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {token}'
        })

        assert resp.status == 200
        data = await resp.json()

        # Verify response structure
        assert 'id' in data
        assert 'username' in data
        assert 'nickname' in data
        assert 'email' in data
        assert 'isActive' in data
        assert 'createTime' in data
        assert 'updateTime' in data

        # Verify response content
        assert data['id'] == test_data['admin_id']
        assert data['username'] == username
        assert data['nickname'] == nickname
        assert data['email'] == f"{username}@example.com"
        assert data['isActive'] is True

        # Verify passwordHash is NOT in response
        assert 'passwordHash' not in data

    @pytest.mark.asyncio
    async def test_get_admin_me_no_token(self, test_admin_cleanup):
        """Test getting current admin info without token"""
        client = test_admin_cleanup['client']

        # Try to access without token
        resp = await client.get('/admin/me')

        # Should be unauthorized (401)
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_get_admin_me_invalid_token(self, test_admin_cleanup):
        """Test getting current admin info with invalid token"""
        client = test_admin_cleanup['client']

        # Try to access with invalid token
        resp = await client.get('/admin/me', headers={
            'Authorization': 'Bearer invalid_token_here'
        })

        # Should be unauthorized (401)
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_get_admin_me_expired_token(self, create_test_admin):
        """Test getting current admin info with expired token"""
        test_data = create_test_admin
        client = test_data['client']

        # Get JwtGateway from app to create expired token
        jwt_gateway: JwtGateway = client.app[absolute_ref(JwtGateway)]

        # Create token that expires immediately
        expired_token = jwt_gateway.encrypt_jwt(
            user_id=str(test_data['admin_id']),
            subject='ADMIN',
            expire_at=int(time.time()) - 3600  # Expired 1 hour ago
        )

        # Try to access with expired token
        resp = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {expired_token}'
        })

        # Should be unauthorized (401)
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_get_admin_me_after_logout(self, create_test_admin):
        """Test getting current admin info after logout"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        password = test_data['password']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })
        assert login_resp.status == 200
        login_data = await login_resp.json()
        token = login_data['token']

        # Get JwtGateway to perform logout
        jwt_gateway: JwtGateway = client.app[absolute_ref(JwtGateway)]

        # Logout by deleting Redis key
        await jwt_gateway.logout(
            user_id=str(test_data['admin_id']),
            user_role='ADMIN'
        )

        # Try to access after logout
        resp = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {token}'
        })

        # Should be unauthorized (401) because Redis login state is gone
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_change_password_success(self, create_test_admin):
        """Test changing password with correct old password"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        old_password = test_data['password']
        new_password = "new_test_password_456"

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': username,
            'password': old_password
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Change password
        resp = await client.put('/admin/change-password', json={
            'oldPassword': old_password,
            'newPassword': new_password,
        }, headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp.status == 200
        data = await resp.json()
        assert data['success'] is True

        # Old password should no longer work
        resp_old = await client.post('/login/admin', json={
            'username': username,
            'password': old_password
        })
        assert resp_old.status == 400

        # New password should work
        resp_new = await client.post('/login/admin', json={
            'username': username,
            'password': new_password
        })
        assert resp_new.status == 200

    @pytest.mark.asyncio
    async def test_change_password_invalid_old_password(self, create_test_admin):
        """Test changing password with wrong old password"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        password = test_data['password']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        resp = await client.put('/admin/change-password', json={
            'oldPassword': 'wrong_old_password',
            'newPassword': 'new_test_password_456',
        }, headers={
            'Authorization': f'Bearer {token}'
        })

        assert resp.status == 400
        resp_text = await resp.text()
        assert 'Invalid old password' in resp_text

    @pytest.mark.asyncio
    async def test_create_admin_success(self, create_test_admin):
        """Test creating a new admin"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        new_username = f"test_admin_created_{test_data['timestamp']}"
        new_nickname = f"nick_created_{test_data['timestamp']}"
        new_password = "created_password_123"
        new_email = f"{new_username}@example.com"
        test_data['track_creation'](new_username)

        resp = await client.post('/admin/admins', json={
            'username': new_username,
            'nickname': new_nickname,
            'password': new_password,
            'email': new_email,
            'isActive': True,
        }, headers={
            'Authorization': f'Bearer {token}'
        })

        assert resp.status == 200
        data = await resp.json()
        assert data['username'] == new_username
        assert data['nickname'] == new_nickname
        assert data['email'] == new_email
        assert data['isActive'] is True
        assert isinstance(data['id'], int)

        # Newly created admin can login
        login_new = await client.post('/login/admin', json={
            'username': new_username,
            'password': new_password
        })
        assert login_new.status == 200

    @pytest.mark.asyncio
    async def test_create_admin_username_exists(self, create_test_admin):
        """Test creating admin when username already exists"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        existing_username = test_data['username']
        resp = await client.post('/admin/admins', json={
            'username': existing_username,
            'nickname': 'duplicate_nick',
            'password': 'some_password_123',
            'email': f"{existing_username}@example.com",
            'isActive': True,
        }, headers={
            'Authorization': f'Bearer {token}'
        })

        assert resp.status == 400
        resp_text = await resp.text()
        assert 'Username already exists' in resp_text

    @pytest.mark.asyncio
    async def test_create_admin_password_too_short(self, create_test_admin):
        """Test creating admin with short password"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        new_username = f"test_admin_short_pwd_{test_data['timestamp']}"
        resp = await client.post('/admin/admins', json={
            'username': new_username,
            'nickname': 'short_pwd_nick',
            'password': '1234567',
            'email': f"{new_username}@example.com",
            'isActive': True,
        }, headers={
            'Authorization': f'Bearer {token}'
        })

        assert resp.status == 400
        resp_text = await resp.text()
        assert 'Password must be at least 8 characters' in resp_text

    @pytest.mark.asyncio
    async def test_get_admin_by_id_success(self, create_test_admin):
        """Test getting admin detail by id"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        new_username = f"test_admin_detail_{test_data['timestamp']}"
        new_nickname = f"nick_detail_{test_data['timestamp']}"
        new_password = "detail_password_123"
        test_data['track_creation'](new_username)

        create_resp = await client.post('/admin/admins', json={
            'username': new_username,
            'nickname': new_nickname,
            'password': new_password,
            'email': f"{new_username}@example.com",
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})
        assert create_resp.status == 200
        created = await create_resp.json()

        admin_id = created['id']
        get_resp = await client.get(f'/admin/admins/{admin_id}', headers={'Authorization': f'Bearer {token}'})
        assert get_resp.status == 200
        detail = await get_resp.json()
        assert detail['id'] == admin_id
        assert detail['username'] == new_username
        assert detail['nickname'] == new_nickname

    @pytest.mark.asyncio
    async def test_update_admin_by_id_success(self, create_test_admin):
        """Test updating admin fields by id"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        original_username = f"test_admin_to_update_{test_data['timestamp']}"
        original_nickname = f"nick_to_update_{test_data['timestamp']}"
        password = "update_password_123"
        test_data['track_creation'](original_username)

        create_resp = await client.post('/admin/admins', json={
            'username': original_username,
            'nickname': original_nickname,
            'password': password,
            'email': f"{original_username}@example.com",
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})
        assert create_resp.status == 200
        created = await create_resp.json()
        admin_id = created['id']

        updated_username = f"test_admin_updated_{test_data['timestamp']}"
        updated_nickname = f"nick_updated_{test_data['timestamp']}"
        updated_email = f"{updated_username}@example.com"
        test_data['track_creation'](updated_username)

        update_resp = await client.put(f'/admin/admins/{admin_id}', json={
            'username': updated_username,
            'nickname': updated_nickname,
            'email': updated_email,
            'isActive': False,
        }, headers={'Authorization': f'Bearer {token}'})
        assert update_resp.status == 200
        updated = await update_resp.json()
        assert updated['id'] == admin_id
        assert updated['username'] == updated_username
        assert updated['nickname'] == updated_nickname
        assert updated['email'] == updated_email
        assert updated['isActive'] is False

        # Login should fail due to inactive
        login_inactive = await client.post('/login/admin', json={
            'username': updated_username,
            'password': password
        })
        assert login_inactive.status == 400

        # Reactivate and verify login works
        reactivate_resp = await client.put(f'/admin/admins/{admin_id}', json={
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})
        assert reactivate_resp.status == 200

        login_active = await client.post('/login/admin', json={
            'username': updated_username,
            'password': password
        })
        assert login_active.status == 200

    @pytest.mark.asyncio
    async def test_update_admin_username_exists(self, create_test_admin):
        """Test updating admin username to an existing one"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        username1 = f"test_admin_u1_{test_data['timestamp']}"
        username2 = f"test_admin_u2_{test_data['timestamp']}"
        test_data['track_creation'](username1)
        test_data['track_creation'](username2)

        resp1 = await client.post('/admin/admins', json={
            'username': username1,
            'nickname': 'nick_u1',
            'password': 'u1_password_123',
            'email': f"{username1}@example.com",
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})
        assert resp1.status == 200
        admin1_id = (await resp1.json())['id']

        resp2 = await client.post('/admin/admins', json={
            'username': username2,
            'nickname': 'nick_u2',
            'password': 'u2_password_123',
            'email': f"{username2}@example.com",
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})
        assert resp2.status == 200

        update_resp = await client.put(f'/admin/admins/{admin1_id}', json={
            'username': username2,
        }, headers={'Authorization': f'Bearer {token}'})
        assert update_resp.status == 400
        resp_text = await update_resp.text()
        assert 'Username already exists' in resp_text

    @pytest.mark.asyncio
    async def test_delete_admin_by_id_success(self, create_test_admin):
        """Test deleting admin by id"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        new_username = f"test_admin_delete_{test_data['timestamp']}"
        test_data['track_creation'](new_username)

        create_resp = await client.post('/admin/admins', json={
            'username': new_username,
            'nickname': 'nick_delete',
            'password': 'delete_password_123',
            'email': f"{new_username}@example.com",
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})
        assert create_resp.status == 200
        created = await create_resp.json()
        admin_id = created['id']

        del_resp = await client.delete(f'/admin/admins/{admin_id}', headers={'Authorization': f'Bearer {token}'})
        assert del_resp.status == 200
        assert (await del_resp.json())['success'] is True

        get_resp = await client.get(f'/admin/admins/{admin_id}', headers={'Authorization': f'Bearer {token}'})
        assert get_resp.status == 404

    @pytest.mark.asyncio
    async def test_default_admin_credentials(self, test_admin_cleanup):
        """Test login with default admin credentials from migration"""
        client = test_admin_cleanup['client']

        # Try to login with default admin (username: admin, password: admin123)
        resp = await client.post('/login/admin', json={
            'username': 'admin',
            'password': 'admin123'
        })

        # Should succeed if the default admin exists
        assert resp.status == 200
        data = await resp.json()
        assert data['username'] == 'admin'
        assert 'token' in data

    @pytest.mark.asyncio
    async def test_jwt_token_validation_flow(self, create_test_admin):
        """Test complete JWT token validation flow"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        password = test_data['password']

        # Step 1: Login
        login_resp = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })
        assert login_resp.status == 200
        login_data = await login_resp.json()
        token = login_data['token']

        # Step 2: Verify Redis login state exists
        jwt_gateway: JwtGateway = client.app[absolute_ref(JwtGateway)]
        is_logged_in = await jwt_gateway.is_logged_in(
            user_id=str(test_data['admin_id']),
            user_role='ADMIN'
        )
        assert is_logged_in is True

        # Step 3: Access protected endpoint successfully
        resp1 = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp1.status == 200

        # Step 4: Logout
        await jwt_gateway.logout(
            user_id=str(test_data['admin_id']),
            user_role='ADMIN'
        )

        # Step 5: Verify Redis login state is gone
        is_logged_in = await jwt_gateway.is_logged_in(
            user_id=str(test_data['admin_id']),
            user_role='ADMIN'
        )
        assert is_logged_in is False

        # Step 6: Access protected endpoint fails after logout
        resp2 = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp2.status == 401

    @pytest.mark.asyncio
    async def test_multiple_login_sessions(self, create_test_admin):
        """Test that multiple logins maintain the same login state"""
        test_data = create_test_admin
        client = test_data['client']
        username = test_data['username']
        password = test_data['password']

        # First login
        resp1 = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })
        assert resp1.status == 200
        data1 = await resp1.json()
        token1 = data1['token']

        # Second login (same user)
        resp2 = await client.post('/login/admin', json={
            'username': username,
            'password': password
        })
        assert resp2.status == 200
        data2 = await resp2.json()
        token2 = data2['token']

        # Both tokens should be valid
        me_resp1 = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {token1}'
        })
        assert me_resp1.status == 200

        me_resp2 = await client.get('/admin/me', headers={
            'Authorization': f'Bearer {token2}'
        })
        assert me_resp2.status == 200

        # Verify both return same admin info
        me_data1 = await me_resp1.json()
        me_data2 = await me_resp2.json()
        assert me_data1['id'] == me_data2['id']
        assert me_data1['username'] == me_data2['username']

    @pytest.mark.asyncio
    async def test_get_admins_basic_pagination(self, create_test_admin):
        """Test basic pagination without filters"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Get admins with default pagination
        resp = await client.get('/admin/admins', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp.status == 200
        data = await resp.json()

        # Verify response structure
        assert 'items' in data
        assert 'offset' in data
        assert 'size' in data
        assert 'total' in data

        # Verify pagination values
        assert data['offset'] == 0
        assert data['size'] == 10
        assert isinstance(data['total'], int)
        assert isinstance(data['items'], list)

        # Verify items structure
        if len(data['items']) > 0:
            first_item = data['items'][0]
            assert 'id' in first_item
            assert 'username' in first_item
            assert 'nickname' in first_item
            assert 'email' in first_item
            assert 'isActive' in first_item
            assert 'createTime' in first_item
            assert 'updateTime' in first_item
            # Ensure no passwordHash in response
            assert 'passwordHash' not in first_item

    @pytest.mark.asyncio
    async def test_get_admins_with_pagination_params(self, create_test_admin):
        """Test pagination with custom offset and size"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Create multiple test admins
        created_usernames = []
        for i in range(5):
            new_username = f"test_admin_page_{test_data['timestamp']}_{i}"
            created_usernames.append(new_username)
            test_data['track_creation'](new_username)

            await client.post('/admin/admins', json={
                'username': new_username,
                'nickname': f'nick_{i}',
                'password': 'password_123',
                'email': f'{new_username}@example.com',
                'isActive': True,
            }, headers={'Authorization': f'Bearer {token}'})

        # Test first page
        resp1 = await client.get('/admin/admins?offset=0&size=2', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp1.status == 200
        data1 = await resp1.json()
        assert data1['offset'] == 0
        assert data1['size'] == 2
        assert len(data1['items']) <= 2

        # Test second page
        resp2 = await client.get('/admin/admins?offset=2&size=2', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp2.status == 200
        data2 = await resp2.json()
        assert data2['offset'] == 2
        assert data2['size'] == 2

        # First and second page items should be different
        if len(data1['items']) > 0 and len(data2['items']) > 0:
            assert data1['items'][0]['id'] != data2['items'][0]['id']

    @pytest.mark.asyncio
    async def test_get_admins_filter_by_username(self, create_test_admin):
        """Test filtering by username (fuzzy match)"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Create test admins with specific usernames
        unique_prefix = f"filter_user_{test_data['timestamp']}"
        usernames = [
            f"{unique_prefix}_alice",
            f"{unique_prefix}_bob",
            f"{unique_prefix}_charlie"
        ]

        for username in usernames:
            test_data['track_creation'](username)
            await client.post('/admin/admins', json={
                'username': username,
                'nickname': f'nick_{username}',
                'password': 'password_123',
                'email': f'{username}@example.com',
                'isActive': True,
            }, headers={'Authorization': f'Bearer {token}'})

        # Filter by partial username
        resp = await client.get('/admin/admins?username=alice', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp.status == 200
        data = await resp.json()

        # Should find alice
        assert data['total'] >= 1
        found_alice = any('alice' in item['username'] for item in data['items'])
        assert found_alice is True

    @pytest.mark.asyncio
    async def test_get_admins_filter_by_nickname(self, create_test_admin):
        """Test filtering by nickname (fuzzy match)"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Create test admin with unique nickname
        unique_nickname = f"unique_nick_{test_data['timestamp']}"
        test_username = f"test_admin_nick_{test_data['timestamp']}"
        test_data['track_creation'](test_username)

        await client.post('/admin/admins', json={
            'username': test_username,
            'nickname': unique_nickname,
            'password': 'password_123',
            'email': f'{test_username}@example.com',
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})

        # Filter by partial nickname
        search_term = unique_nickname[:10]
        resp = await client.get(f'/admin/admins?nickname={search_term}', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp.status == 200
        data = await resp.json()

        # Should find the admin with matching nickname
        assert data['total'] >= 1
        found = any(search_term in item['nickname'] for item in data['items'])
        assert found is True

    @pytest.mark.asyncio
    async def test_get_admins_filter_by_email(self, create_test_admin):
        """Test filtering by email (fuzzy match)"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Create test admin with unique email
        test_username = f"test_admin_email_{test_data['timestamp']}"
        unique_email = f"unique_{test_data['timestamp']}@example.com"
        test_data['track_creation'](test_username)

        await client.post('/admin/admins', json={
            'username': test_username,
            'nickname': 'email_nick',
            'password': 'password_123',
            'email': unique_email,
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})

        # Filter by partial email
        search_term = f"unique_{test_data['timestamp']}"
        resp = await client.get(f'/admin/admins?email={search_term}', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp.status == 200
        data = await resp.json()

        # Should find the admin with matching email
        assert data['total'] >= 1
        found = any(search_term in (item['email'] or '') for item in data['items'])
        assert found is True

    @pytest.mark.asyncio
    async def test_get_admins_filter_by_is_active(self, create_test_admin):
        """Test filtering by isActive status"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Create active admin
        active_username = f"test_admin_active_{test_data['timestamp']}"
        test_data['track_creation'](active_username)
        await client.post('/admin/admins', json={
            'username': active_username,
            'nickname': 'active_nick',
            'password': 'password_123',
            'email': f'{active_username}@example.com',
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})

        # Create inactive admin
        inactive_username = f"test_admin_inactive_{test_data['timestamp']}"
        test_data['track_creation'](inactive_username)
        await client.post('/admin/admins', json={
            'username': inactive_username,
            'nickname': 'inactive_nick',
            'password': 'password_123',
            'email': f'{inactive_username}@example.com',
            'isActive': False,
        }, headers={'Authorization': f'Bearer {token}'})

        # Filter by active=true
        resp_active = await client.get('/admin/admins?isActive=true', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp_active.status == 200
        data_active = await resp_active.json()

        # All items should be active
        for item in data_active['items']:
            assert item['isActive'] is True

        # Filter by active=false
        resp_inactive = await client.get('/admin/admins?isActive=false', headers={
            'Authorization': f'Bearer {token}'
        })
        assert resp_inactive.status == 200
        data_inactive = await resp_inactive.json()

        # All items should be inactive
        for item in data_inactive['items']:
            assert item['isActive'] is False

    @pytest.mark.asyncio
    async def test_get_admins_multiple_filters(self, create_test_admin):
        """Test using multiple filters together"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Create test admin
        test_username = f"test_multi_{test_data['timestamp']}"
        test_nickname = f"multi_nick_{test_data['timestamp']}"
        test_data['track_creation'](test_username)

        await client.post('/admin/admins', json={
            'username': test_username,
            'nickname': test_nickname,
            'password': 'password_123',
            'email': f'{test_username}@example.com',
            'isActive': True,
        }, headers={'Authorization': f'Bearer {token}'})

        # Use multiple filters
        resp = await client.get(
            '/admin/admins?username=multi&isActive=true',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp.status == 200
        data = await resp.json()

        # All results should match both filters
        for item in data['items']:
            assert 'multi' in item['username']
            assert item['isActive'] is True

    @pytest.mark.asyncio
    async def test_get_admins_no_auth(self, test_admin_cleanup):
        """Test accessing get_admins without authentication"""
        client = test_admin_cleanup['client']

        # Try to access without token
        resp = await client.get('/admin/admins')

        # Should be unauthorized (401)
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_get_admins_empty_result(self, create_test_admin):
        """Test filtering with no matching results"""
        test_data = create_test_admin
        client = test_data['client']

        # Login to get token
        login_resp = await client.post('/login/admin', json={
            'username': test_data['username'],
            'password': test_data['password']
        })
        assert login_resp.status == 200
        token = (await login_resp.json())['token']

        # Search for non-existent username
        resp = await client.get(
            '/admin/admins?username=definitely_does_not_exist_99999',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp.status == 200
        data = await resp.json()

        # Should return empty list
        assert data['total'] == 0
        assert data['items'] == []
        assert data['offset'] == 0
        assert data['size'] == 10
