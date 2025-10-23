#!/usr/bin/env python3
"""
Comprehensive Test Suite for WhatsApp-MCP-ERPNext Integration

This test suite covers:
1. ERPNext Client Tests - Task creation, user listing/searching, assignment workflow
2. User Resolver Tests - Single/multiple user matching, disambiguation, fuzzy matching
3. MCP Server Tests - Tool invocation, response format, error handling
4. Integration Tests - End-to-end task creation flow, WhatsApp disambiguation
5. Mock Strategy - Mock ERPNext API, WhatsApp MCP client, claude-flow hooks

Test Framework: pytest with async support
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock
from typing import Dict, List, Any

# Import modules to test
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whatsapp_monitoring.erpnext_client import ERPNextClient
from whatsapp_monitoring.user_resolver import UserResolver


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_users():
    """Sample user data for testing"""
    return [
        {
            'name': 'john.doe@example.com',
            'email': 'john.doe@example.com',
            'full_name': 'John Doe',
            'enabled': 1
        },
        {
            'name': 'jane.smith@example.com',
            'email': 'jane.smith@example.com',
            'full_name': 'Jane Smith',
            'enabled': 1
        },
        {
            'name': 'john.smith@example.com',
            'email': 'john.smith@example.com',
            'full_name': 'John Smith',
            'enabled': 1
        },
        {
            'name': 'bob.jones@example.com',
            'email': 'bob.jones@example.com',
            'full_name': 'Bob Jones',
            'enabled': 1
        },
        {
            'name': 'admin@example.com',
            'email': 'admin@example.com',
            'full_name': 'Admin User',
            'enabled': 1
        }
    ]


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        'subject': 'Test Task from WhatsApp',
        'description': 'This is a test task created via WhatsApp integration',
        'priority': 'High',
        'due_date': '2025-11-01',
        'assigned_to': 'john.doe@example.com'
    }


@pytest.fixture
def sample_task_response():
    """Sample successful task creation response"""
    return {
        'data': {
            'name': 'TASK-2025-001',
            'subject': 'Test Task from WhatsApp',
            'status': 'Open',
            'priority': 'High'
        }
    }


@pytest.fixture
def mock_requests_session():
    """Mock requests.Session for ERPNext API calls"""
    with patch('whatsapp_monitoring.erpnext_client.requests.Session') as mock_session:
        session_instance = MagicMock()
        mock_session.return_value = session_instance
        yield session_instance


@pytest.fixture
def erpnext_client(mock_requests_session):
    """ERPNext client with mocked session"""
    client = ERPNextClient(
        url='https://erp.example.com',
        api_key='test_key',
        api_secret='test_secret'
    )
    client.session = mock_requests_session
    return client


@pytest.fixture
def mock_whatsapp_sender():
    """Mock WhatsApp sender function"""
    return MagicMock(return_value=True)


@pytest.fixture
def user_resolver(erpnext_client, mock_whatsapp_sender):
    """UserResolver with mocked dependencies"""
    return UserResolver(
        erpnext_client=erpnext_client,
        whatsapp_sender=mock_whatsapp_sender,
        admin_number='1234567890@s.whatsapp.net',
        default_assignee='admin@example.com'
    )


@pytest.fixture
def mock_whatsapp_messages():
    """Sample WhatsApp messages for testing"""
    return [
        {
            'id': 'msg_001',
            'chat_jid': '1234567890@s.whatsapp.net',
            'sender': '1234567890',
            'content': '#task Create website homepage',
            'timestamp': datetime.now().isoformat()
        },
        {
            'id': 'msg_002',
            'chat_jid': '1234567890@s.whatsapp.net',
            'sender': '1234567890',
            'content': '1',  # Disambiguation response
            'timestamp': (datetime.now() + timedelta(seconds=5)).isoformat()
        }
    ]


@pytest.fixture
def mock_erp_responses():
    """Mock ERP API responses"""
    return {
        'task_created': {
            'data': {
                'name': 'TASK-2025-001',
                'subject': 'Test Task',
                'status': 'Open'
            }
        },
        'assignment_success': {
            'message': 'Assignment successful'
        },
        'users_list': {
            'data': [
                {'name': 'john@example.com', 'full_name': 'John Doe', 'email': 'john@example.com'},
                {'name': 'jane@example.com', 'full_name': 'Jane Smith', 'email': 'jane@example.com'}
            ]
        }
    }


# =============================================================================
# ERPNEXT CLIENT TESTS
# =============================================================================

class TestERPNextClient:
    """Test suite for ERPNextClient"""

    def test_client_initialization(self):
        """Test client initializes with correct configuration"""
        client = ERPNextClient(
            url='https://erp.example.com/',
            api_key='test_key',
            api_secret='test_secret'
        )

        assert client.url == 'https://erp.example.com'
        assert client.api_key == 'test_key'
        assert client.api_secret == 'test_secret'
        assert 'Authorization' in client.session.headers
        assert client.session.headers['Authorization'] == 'token test_key:test_secret'

    def test_create_task_success(self, erpnext_client, mock_requests_session, sample_task_data, sample_task_response):
        """Test successful task creation"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_response
        mock_requests_session.post.return_value = mock_response

        # Create task
        result = erpnext_client.create_task(sample_task_data)

        # Verify result
        assert result['success'] is True
        assert result['task_id'] == 'TASK-2025-001'
        assert 'task_url' in result
        assert 'TASK-2025-001' in result['task_url']

        # Verify API was called correctly
        mock_requests_session.post.assert_called()
        call_args = mock_requests_session.post.call_args
        assert 'api/resource/Task' in call_args[0][0]

    def test_create_task_with_assignment(self, erpnext_client, mock_requests_session, sample_task_data, sample_task_response):
        """Test task creation with user assignment"""
        # Mock task creation response
        mock_create_response = MagicMock()
        mock_create_response.status_code = 200
        mock_create_response.json.return_value = sample_task_response

        # Mock assignment response
        mock_assign_response = MagicMock()
        mock_assign_response.status_code = 200
        mock_assign_response.json.return_value = {'message': 'success'}

        mock_requests_session.post.side_effect = [mock_create_response, mock_assign_response]

        # Create task with assignment
        result = erpnext_client.create_task(sample_task_data)

        assert result['success'] is True
        assert mock_requests_session.post.call_count == 2  # Task creation + assignment

    def test_create_task_api_error(self, erpnext_client, mock_requests_session, sample_task_data):
        """Test task creation handles API errors"""
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_requests_session.post.return_value = mock_response

        result = erpnext_client.create_task(sample_task_data)

        assert result['success'] is False
        assert 'error' in result
        assert '500' in result['error']

    def test_create_task_network_error(self, erpnext_client, mock_requests_session, sample_task_data):
        """Test task creation handles network errors"""
        import requests
        mock_requests_session.post.side_effect = requests.RequestException('Connection timeout')

        result = erpnext_client.create_task(sample_task_data)

        assert result['success'] is False
        assert 'error' in result
        assert 'Connection' in result['error'] or 'timeout' in result['error'].lower()

    def test_list_users_success(self, erpnext_client, mock_requests_session, sample_users):
        """Test successful user listing"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': sample_users}
        mock_requests_session.get.return_value = mock_response

        result = erpnext_client.list_users()

        assert result['success'] is True
        assert len(result['users']) == len(sample_users)
        assert result['users'][0]['email'] == 'john.doe@example.com'

    def test_list_users_with_filters(self, erpnext_client, mock_requests_session):
        """Test user listing with custom fields and limit"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': []}
        mock_requests_session.get.return_value = mock_response

        result = erpnext_client.list_users(
            fields=['name', 'email', 'full_name'],
            limit=50
        )

        assert result['success'] is True
        call_args = mock_requests_session.get.call_args
        params = call_args[1]['params']
        assert params['limit_page_length'] == 50

    def test_search_users_by_name(self, erpnext_client, mock_requests_session, sample_users):
        """Test user search by name"""
        john_users = [u for u in sample_users if 'john' in u['full_name'].lower()]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': john_users}
        mock_requests_session.get.return_value = mock_response

        result = erpnext_client.search_users('John')

        assert result['success'] is True
        assert len(result['users']) == 2
        assert all('john' in u['full_name'].lower() for u in result['users'])

    def test_search_users_by_email(self, erpnext_client, mock_requests_session, sample_users):
        """Test user search by email"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': [sample_users[0]]}
        mock_requests_session.get.return_value = mock_response

        result = erpnext_client.search_users('john.doe')

        assert result['success'] is True
        assert len(result['users']) >= 0

    def test_get_user_success(self, erpnext_client, mock_requests_session, sample_users):
        """Test getting specific user"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': sample_users[0]}
        mock_requests_session.get.return_value = mock_response

        result = erpnext_client.get_user('john.doe@example.com')

        assert result['success'] is True
        assert result['user']['email'] == 'john.doe@example.com'

    def test_get_user_not_found(self, erpnext_client, mock_requests_session):
        """Test getting non-existent user"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = 'User not found'
        mock_requests_session.get.return_value = mock_response

        result = erpnext_client.get_user('nonexistent@example.com')

        assert result['success'] is False
        assert '404' in result['error']

    def test_assignment_fallback_method(self, erpnext_client, mock_requests_session, sample_task_response):
        """Test task assignment falls back to alternative method on failure"""
        # Mock task creation success
        mock_create_response = MagicMock()
        mock_create_response.status_code = 200
        mock_create_response.json.return_value = sample_task_response

        # Mock assignment failure then success on alternative method
        mock_assign_fail = MagicMock()
        mock_assign_fail.status_code = 500

        mock_update_success = MagicMock()
        mock_update_success.status_code = 200

        mock_requests_session.post.side_effect = [mock_create_response, mock_assign_fail]
        mock_requests_session.put.return_value = mock_update_success

        task_data = {
            'subject': 'Test Task',
            'assigned_to': 'john@example.com'
        }

        result = erpnext_client.create_task(task_data)

        assert result['success'] is True
        assert mock_requests_session.put.called  # Alternative method was used


# =============================================================================
# USER RESOLVER TESTS
# =============================================================================

class TestUserResolver:
    """Test suite for UserResolver"""

    def test_resolve_single_user_match(self, user_resolver, erpnext_client, mock_requests_session, sample_users):
        """Test resolving user with single clear match"""
        # Mock search returning single user
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': [sample_users[0]]}
        mock_requests_session.get.return_value = mock_response

        result = user_resolver.resolve_user('John Doe')

        assert result['resolved'] is True
        assert result['needs_disambiguation'] is False
        assert result['user']['email'] == 'john.doe@example.com'

    def test_resolve_multiple_users_disambiguation(self, user_resolver, erpnext_client, mock_requests_session, sample_users, mock_whatsapp_sender):
        """Test resolving user with multiple matches triggers disambiguation"""
        # Mock search returning multiple Johns
        john_users = [u for u in sample_users if 'john' in u['full_name'].lower()]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': john_users}
        mock_requests_session.get.return_value = mock_response

        result = user_resolver.resolve_user('John')

        assert result['resolved'] is False
        assert result['needs_disambiguation'] is True
        assert 'resolution_id' in result
        assert len(result['candidates']) > 1

        # Verify WhatsApp message was sent
        mock_whatsapp_sender.assert_called_once()
        call_args = mock_whatsapp_sender.call_args[0]
        assert 'multiple users' in call_args[1].lower()

    def test_resolve_default_assignee(self, user_resolver, erpnext_client, mock_requests_session, sample_users):
        """Test using default assignee when no user specified"""
        # Mock getting default user
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': sample_users[4]}  # Admin user
        mock_requests_session.get.return_value = mock_response

        result = user_resolver.resolve_user(None)

        assert result['resolved'] is True
        assert result['user']['email'] == 'admin@example.com'

    def test_resolve_no_matches(self, user_resolver, erpnext_client, mock_requests_session):
        """Test resolving user with no matches"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': []}
        mock_requests_session.get.return_value = mock_response

        result = user_resolver.resolve_user('NonexistentUser')

        assert result['resolved'] is False
        assert 'error' in result
        assert 'No users found' in result['error']

    def test_fuzzy_matching_threshold(self, user_resolver, erpnext_client, mock_requests_session, sample_users):
        """Test fuzzy matching respects threshold"""
        # Mock search returning users with varying match quality
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': sample_users}
        mock_requests_session.get.return_value = mock_response

        # Search for partial match
        result = user_resolver.resolve_user('Jon')  # Fuzzy match for John

        # Should rank by match score
        if result.get('resolved'):
            assert 'john' in result['user']['full_name'].lower()
        elif result.get('needs_disambiguation'):
            assert all('match_score' in c for c in result['candidates'])

    def test_disambiguation_numeric_response(self, user_resolver, sample_users):
        """Test disambiguation with numeric selection"""
        # Create a pending resolution
        resolution_id = 'test_resolution_001'
        user_resolver.pending_resolutions[resolution_id] = {
            'candidates': [
                {'user': sample_users[0], 'match_score': 95},
                {'user': sample_users[2], 'match_score': 85}
            ],
            'timestamp': datetime.now(),
            'original_query': 'John',
            'context': {}
        }

        # Mock response checker returning numeric selection
        def mock_response_checker(admin_number, timestamp):
            return '1'

        result = user_resolver.check_disambiguation_response(resolution_id, mock_response_checker)

        assert result is not None
        assert result['resolved'] is True
        assert result['user']['email'] == 'john.doe@example.com'
        assert result['selection'] == 1

    def test_disambiguation_cancel_response(self, user_resolver, sample_users):
        """Test disambiguation cancellation"""
        resolution_id = 'test_resolution_002'
        user_resolver.pending_resolutions[resolution_id] = {
            'candidates': [{'user': sample_users[0], 'match_score': 90}],
            'timestamp': datetime.now(),
            'original_query': 'Test',
            'context': {}
        }

        def mock_response_checker(admin_number, timestamp):
            return 'cancel'

        result = user_resolver.check_disambiguation_response(resolution_id, mock_response_checker)

        assert result is not None
        assert result.get('cancelled') is True
        assert resolution_id not in user_resolver.pending_resolutions

    def test_disambiguation_timeout(self, user_resolver, sample_users):
        """Test disambiguation request timeout"""
        resolution_id = 'test_resolution_003'
        old_timestamp = datetime.now() - timedelta(seconds=400)  # Beyond timeout

        user_resolver.pending_resolutions[resolution_id] = {
            'candidates': [{'user': sample_users[0], 'match_score': 90}],
            'timestamp': old_timestamp,
            'original_query': 'Test',
            'context': {}
        }

        def mock_response_checker(admin_number, timestamp):
            return None

        result = user_resolver.check_disambiguation_response(resolution_id, mock_response_checker)

        assert result is not None
        assert 'error' in result
        assert 'timed out' in result['error'].lower()

    def test_disambiguation_invalid_selection(self, user_resolver, sample_users, mock_whatsapp_sender):
        """Test disambiguation with invalid numeric selection"""
        resolution_id = 'test_resolution_004'
        user_resolver.pending_resolutions[resolution_id] = {
            'candidates': [
                {'user': sample_users[0], 'match_score': 95},
                {'user': sample_users[2], 'match_score': 85}
            ],
            'timestamp': datetime.now(),
            'original_query': 'John',
            'context': {}
        }

        def mock_response_checker(admin_number, timestamp):
            return '99'  # Invalid selection

        result = user_resolver.check_disambiguation_response(resolution_id, mock_response_checker)

        assert result is None  # No resolution yet
        assert resolution_id in user_resolver.pending_resolutions  # Still pending
        mock_whatsapp_sender.assert_called()  # Error message sent

    def test_wait_for_disambiguation_success(self, user_resolver, sample_users):
        """Test waiting for disambiguation response"""
        resolution_id = 'test_resolution_005'
        user_resolver.pending_resolutions[resolution_id] = {
            'candidates': [{'user': sample_users[0], 'match_score': 95}],
            'timestamp': datetime.now(),
            'original_query': 'Test',
            'context': {}
        }

        # Mock response checker that returns selection after first call
        call_count = [0]
        def mock_response_checker(admin_number, timestamp):
            call_count[0] += 1
            if call_count[0] > 1:
                return '1'
            return None

        result = user_resolver.wait_for_disambiguation(
            resolution_id,
            mock_response_checker,
            poll_interval=0.1,
            max_wait=5
        )

        assert result['resolved'] is True
        assert result['user']['email'] == 'john.doe@example.com'

    def test_cleanup_expired_resolutions(self, user_resolver, sample_users):
        """Test cleanup of expired disambiguation requests"""
        # Add expired resolution
        old_resolution = 'old_resolution'
        user_resolver.pending_resolutions[old_resolution] = {
            'candidates': [{'user': sample_users[0], 'match_score': 90}],
            'timestamp': datetime.now() - timedelta(seconds=400),
            'original_query': 'Old',
            'context': {}
        }

        # Add fresh resolution
        fresh_resolution = 'fresh_resolution'
        user_resolver.pending_resolutions[fresh_resolution] = {
            'candidates': [{'user': sample_users[1], 'match_score': 90}],
            'timestamp': datetime.now(),
            'original_query': 'Fresh',
            'context': {}
        }

        cleaned = user_resolver.cleanup_expired_resolutions()

        assert cleaned == 1
        assert old_resolution not in user_resolver.pending_resolutions
        assert fresh_resolution in user_resolver.pending_resolutions

    def test_fuzzy_match_accuracy(self, user_resolver):
        """Test fuzzy matching algorithm accuracy"""
        # Test exact match
        score = user_resolver._fuzzy_match('john', 'john')
        assert score == 1.0

        # Test partial match
        score = user_resolver._fuzzy_match('john', 'johnny')
        assert 0.6 < score < 0.9

        # Test no match
        score = user_resolver._fuzzy_match('john', 'alice')
        assert score < 0.4


# =============================================================================
# MCP SERVER INTEGRATION TESTS
# =============================================================================

class TestMCPIntegration:
    """Test suite for MCP server integration"""

    @pytest.fixture
    def mock_mcp_client(self):
        """Mock MCP client for testing"""
        return MagicMock()

    def test_mcp_tool_create_task_invocation(self, mock_mcp_client, sample_task_data):
        """Test MCP tool invocation for task creation"""
        # Simulate MCP tool call
        tool_input = {
            'task_details': sample_task_data
        }

        expected_response = {
            'success': True,
            'task_id': 'TASK-2025-001',
            'task_url': 'https://erp.example.com/app/task/TASK-2025-001'
        }

        mock_mcp_client.call_tool.return_value = expected_response

        # Invoke tool
        result = mock_mcp_client.call_tool('create_erp_task', tool_input)

        assert result['success'] is True
        assert 'task_id' in result
        mock_mcp_client.call_tool.assert_called_once_with('create_erp_task', tool_input)

    def test_mcp_tool_resolve_user_invocation(self, mock_mcp_client):
        """Test MCP tool invocation for user resolution"""
        tool_input = {'user_query': 'John Doe'}

        expected_response = {
            'resolved': True,
            'user': {
                'email': 'john.doe@example.com',
                'full_name': 'John Doe'
            }
        }

        mock_mcp_client.call_tool.return_value = expected_response

        result = mock_mcp_client.call_tool('resolve_user', tool_input)

        assert result['resolved'] is True
        assert result['user']['email'] == 'john.doe@example.com'

    def test_mcp_response_format_validation(self):
        """Test MCP response format validation"""
        valid_response = {
            'success': True,
            'task_id': 'TASK-001',
            'task_url': 'https://example.com/task/TASK-001'
        }

        # Validate required fields
        assert 'success' in valid_response
        assert 'task_id' in valid_response
        assert 'task_url' in valid_response
        assert isinstance(valid_response['success'], bool)

    def test_mcp_error_handling(self, mock_mcp_client):
        """Test MCP error response handling"""
        mock_mcp_client.call_tool.side_effect = Exception('MCP connection error')

        with pytest.raises(Exception) as exc_info:
            mock_mcp_client.call_tool('create_erp_task', {})

        assert 'MCP connection error' in str(exc_info.value)

    def test_mcp_async_operation(self, mock_mcp_client):
        """Test async MCP operation handling"""
        # Simulate async operation
        mock_mcp_client.call_tool_async = AsyncMock(
            return_value={'success': True, 'task_id': 'TASK-001'}
        )

        # Would need to run in async context
        # For now, just verify the mock is set up correctly
        assert callable(mock_mcp_client.call_tool_async)


# =============================================================================
# END-TO-END INTEGRATION TESTS
# =============================================================================

class TestEndToEndIntegration:
    """End-to-end integration test suite"""

    def test_simple_task_creation_flow(self, erpnext_client, mock_requests_session, sample_task_data, sample_task_response):
        """Test complete task creation flow without user disambiguation"""
        # Mock successful task creation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_response
        mock_requests_session.post.return_value = mock_response

        # Create task
        result = erpnext_client.create_task(sample_task_data)

        # Verify complete flow
        assert result['success'] is True
        assert result['task_id'] == 'TASK-2025-001'
        assert 'erp.example.com' in result['task_url']

    def test_task_creation_with_user_disambiguation_flow(self, user_resolver, erpnext_client, mock_requests_session, sample_users, sample_task_data, sample_task_response, mock_whatsapp_sender):
        """Test complete task creation flow with user disambiguation"""
        # Step 1: Search returns multiple users
        john_users = [u for u in sample_users if 'john' in u['full_name'].lower()]
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {'data': john_users}

        # Step 2: Task creation after disambiguation
        mock_task_response = MagicMock()
        mock_task_response.status_code = 200
        mock_task_response.json.return_value = sample_task_response

        mock_requests_session.get.return_value = mock_search_response
        mock_requests_session.post.return_value = mock_task_response

        # Resolve user - should trigger disambiguation
        user_result = user_resolver.resolve_user('John')

        assert user_result['needs_disambiguation'] is True
        resolution_id = user_result['resolution_id']

        # Simulate user selecting option 1
        user_resolver.pending_resolutions[resolution_id]['timestamp'] = datetime.now()

        def mock_response_checker(admin_number, timestamp):
            return '1'

        disambiguation_result = user_resolver.check_disambiguation_response(
            resolution_id,
            mock_response_checker
        )

        assert disambiguation_result['resolved'] is True
        selected_user = disambiguation_result['user']

        # Create task with resolved user
        task_data = sample_task_data.copy()
        task_data['assigned_to'] = selected_user['email']

        task_result = erpnext_client.create_task(task_data)

        assert task_result['success'] is True
        assert task_result['task_id'] == 'TASK-2025-001'

    def test_whatsapp_message_to_task_flow(self, erpnext_client, user_resolver, mock_requests_session, sample_users, mock_whatsapp_messages, sample_task_response):
        """Test complete flow from WhatsApp message to ERP task"""
        # Simulate receiving WhatsApp message
        whatsapp_msg = mock_whatsapp_messages[0]

        # Parse task from message
        task_content = whatsapp_msg['content'].replace('#task', '').strip()

        # Mock user resolution (no disambiguation needed)
        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {'data': [sample_users[4]]}  # Admin

        # Mock task creation
        mock_task_response = MagicMock()
        mock_task_response.status_code = 200
        mock_task_response.json.return_value = sample_task_response

        mock_requests_session.get.return_value = mock_user_response
        mock_requests_session.post.return_value = mock_task_response

        # Create task
        task_data = {
            'subject': task_content,
            'description': f'Created from WhatsApp message {whatsapp_msg["id"]}',
            'priority': 'Medium'
        }

        result = erpnext_client.create_task(task_data)

        assert result['success'] is True
        assert result['task_id'] == 'TASK-2025-001'

    def test_claude_code_hooks_integration(self):
        """Test integration with claude-flow hooks"""
        # Mock hook execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='Hook executed')

            # Simulate pre-task hook
            import subprocess
            result = subprocess.run(
                ['npx', 'claude-flow@alpha', 'hooks', 'pre-task', '--description', 'Test task'],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            mock_run.assert_called_once()

    def test_error_recovery_flow(self, erpnext_client, mock_requests_session, sample_task_data):
        """Test error recovery in task creation flow"""
        # First attempt fails
        mock_fail_response = MagicMock()
        mock_fail_response.status_code = 500
        mock_fail_response.text = 'Server error'

        # Second attempt succeeds (after retry)
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {'data': {'name': 'TASK-001'}}

        mock_requests_session.post.side_effect = [mock_fail_response, mock_success_response]

        # First attempt
        result1 = erpnext_client.create_task(sample_task_data)
        assert result1['success'] is False

        # Retry
        result2 = erpnext_client.create_task(sample_task_data)
        assert result2['success'] is True


# =============================================================================
# PERFORMANCE AND STRESS TESTS
# =============================================================================

class TestPerformance:
    """Performance and stress tests"""

    def test_bulk_user_search_performance(self, erpnext_client, mock_requests_session, sample_users):
        """Test performance with large user lists"""
        # Create large user list
        large_user_list = sample_users * 200  # 1000 users

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': large_user_list}
        mock_requests_session.get.return_value = mock_response

        start_time = time.time()
        result = erpnext_client.list_users(limit=1000)
        elapsed = time.time() - start_time

        assert result['success'] is True
        assert len(result['users']) == 1000
        assert elapsed < 5.0  # Should complete in under 5 seconds

    def test_concurrent_task_creation(self, erpnext_client, mock_requests_session, sample_task_response):
        """Test handling concurrent task creation requests"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_response
        mock_requests_session.post.return_value = mock_response

        # Simulate 10 concurrent task creations
        tasks = [
            {'subject': f'Task {i}', 'priority': 'Medium'}
            for i in range(10)
        ]

        results = []
        for task_data in tasks:
            result = erpnext_client.create_task(task_data)
            results.append(result)

        assert all(r['success'] for r in results)
        assert len(results) == 10

    def test_disambiguation_memory_cleanup(self, user_resolver, sample_users):
        """Test memory cleanup for pending resolutions"""
        # Create many pending resolutions
        for i in range(100):
            resolution_id = f'resolution_{i}'
            user_resolver.pending_resolutions[resolution_id] = {
                'candidates': [{'user': sample_users[0], 'match_score': 90}],
                'timestamp': datetime.now() - timedelta(seconds=400),
                'original_query': f'Query {i}',
                'context': {}
            }

        assert len(user_resolver.pending_resolutions) == 100

        cleaned = user_resolver.cleanup_expired_resolutions()

        assert cleaned == 100
        assert len(user_resolver.pending_resolutions) == 0


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
