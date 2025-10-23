# WhatsApp Monitoring MCP Server - Usage Examples

This document provides practical examples of using the WhatsApp Monitoring MCP server with Claude Code.

## Prerequisites

1. MCP server configured in Claude Code (see `claude_mcp_config.json`)
2. ERPNext credentials configured in `config/settings.env`
3. WhatsApp MCP client available in Claude Code

## Example 1: Simple Task Creation

Create a task with automatic user assignment:

```python
# Claude Code will call this via MCP
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Review quarterly reports",
    "description": "Review Q4 financial reports and prepare summary",
    "priority": "High",
    "due_date": "2025-10-30"
})

# Response
{
  "success": true,
  "task_id": "TASK-00456",
  "task_url": "https://erp.walnutedu.in/app/task/TASK-00456",
  "subject": "Review quarterly reports",
  "priority": "High"
}
```

## Example 2: Task Creation with User Assignment

Create a task assigned to a specific user:

```python
# Automatically resolve user "John" and create task
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Update API documentation",
    "description": "Document new REST endpoints for mobile app",
    "priority": "Medium",
    "due_date": "2025-11-01",
    "assigned_to": "john",
    "auto_resolve": True  # Default, will auto-select best match
})

# Response
{
  "success": true,
  "task_id": "TASK-00457",
  "task_url": "https://erp.walnutedu.in/app/task/TASK-00457",
  "subject": "Update API documentation",
  "priority": "Medium",
  "assigned_to": "john.doe@example.com",
  "user_resolution": {
    "resolved": true,
    "user": "John Doe (john.doe@example.com) - Active",
    "match_score": 95
  }
}
```

## Example 3: Interactive User Resolution

Handle cases where multiple users match a query:

```python
# Step 1: Try to create task (will fail with disambiguation needed)
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Fix mobile app crash",
    "assigned_to": "smith",
    "auto_resolve": False  # Force interactive resolution
})

# Response indicates disambiguation needed
{
  "success": false,
  "needs_disambiguation": true,
  "resolution_id": "user_resolve_1729614000123",
  "candidates": [
    {
      "user": "John Smith (john.smith@example.com) - Active",
      "match_score": 88,
      "email": "john.smith@example.com"
    },
    {
      "user": "Jane Smith (jane.smith@example.com) - Active",
      "match_score": 85,
      "email": "jane.smith@example.com"
    }
  ],
  "message": "Multiple users found. Use resolve_user_interactive or select auto_resolve=true"
}

# Step 2: Start interactive resolution
resolution = mcp__whatsapp_monitoring__resolve_user_interactive({
    "query": "smith"
})

# Admin receives WhatsApp message:
# "🔍 Found multiple users matching 'smith':
#  1. John Smith (john.smith@example.com) - 88% match
#  2. Jane Smith (jane.smith@example.com) - 85% match
#  Reply with the number (1-2) to select a user, or 'cancel' to abort."

# Step 3: Poll for admin response
disambiguation = mcp__whatsapp_monitoring__check_disambiguation({
    "resolution_id": "user_resolve_1729614000123",
    "wait": True,
    "timeout": 120  # Wait up to 2 minutes
})

# Response (after admin selects option 1)
{
  "success": true,
  "resolved": true,
  "user": "John Smith (john.smith@example.com) - Active",
  "email": "john.smith@example.com",
  "username": "john.smith@example.com",
  "selection": 1
}

# Step 4: Create task with resolved user
final_task = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Fix mobile app crash",
    "assigned_to": "john.smith@example.com"
})
```

## Example 4: User Search and Validation

Search for users before creating a task:

```python
# Search for users matching "developer"
users = mcp__whatsapp_monitoring__search_users({
    "query": "developer"
})

# Response
{
  "success": true,
  "query": "developer",
  "count": 3,
  "users": [
    {
      "name": "Senior Developer",
      "email": "senior.dev@example.com",
      "username": "senior.dev@example.com",
      "match_score": 92,
      "enabled": true
    },
    {
      "name": "Junior Developer",
      "email": "junior.dev@example.com",
      "username": "junior.dev@example.com",
      "match_score": 90,
      "enabled": true
    },
    {
      "name": "Developer Lead",
      "email": "dev.lead@example.com",
      "username": "dev.lead@example.com",
      "match_score": 88,
      "enabled": true
    }
  ]
}

# Create task with validated user
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Code review for PR #123",
    "assigned_to": users["users"][0]["email"]  # Use exact email
})
```

## Example 5: Listing All Users

Get a list of all active ERPNext users:

```python
# List first 100 users
users = mcp__whatsapp_monitoring__list_erp_users({
    "limit": 100
})

# Response
{
  "success": true,
  "count": 42,
  "users": [
    {
      "name": "John Doe",
      "email": "john.doe@example.com",
      "username": "john.doe@example.com",
      "enabled": true
    },
    // ... more users
  ]
}

# Use this to build a user selection UI or validate assignments
```

## Example 6: Batch Task Creation

Create multiple tasks with different assignees:

```python
# Define tasks
tasks_to_create = [
    {
        "subject": "Review architecture design",
        "assigned_to": "architect",
        "priority": "High",
        "due_date": "2025-10-28"
    },
    {
        "subject": "Update test coverage",
        "assigned_to": "tester",
        "priority": "Medium",
        "due_date": "2025-10-29"
    },
    {
        "subject": "Deploy to staging",
        "assigned_to": "devops",
        "priority": "High",
        "due_date": "2025-10-27"
    }
]

# Create all tasks
results = []
for task_data in tasks_to_create:
    result = mcp__whatsapp_monitoring__create_erp_task({
        **task_data,
        "auto_resolve": True
    })
    results.append(result)

# Check results
successful = [r for r in results if r.get("success")]
failed = [r for r in results if not r.get("success")]

print(f"Created {len(successful)} tasks successfully")
print(f"Failed: {len(failed)} tasks")
```

## Example 7: Task Creation from WhatsApp Message

Process a WhatsApp message and create a task:

```python
# Get WhatsApp messages with #task tag
messages = mcp__whatsapp__list_messages({
    "query": "#task",
    "limit": 1
})

# Parse message content
message = messages[0]
text = message["text"]

# Extract task details (simple example)
# "#task Fix login bug - urgent"
parts = text.replace("#task", "").strip().split(" - ")
subject = parts[0]
priority = parts[1] if len(parts) > 1 else "Medium"

# Create task
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": subject,
    "priority": priority.capitalize(),
    "description": f"Created from WhatsApp message by {message['sender_name']}"
})

# Send confirmation back to WhatsApp
if result["success"]:
    mcp__whatsapp__send_message({
        "recipient": message["sender_phone"],
        "message": f"✅ Task created: {result['task_id']}\n{result['task_url']}"
    })
```

## Example 8: Smart User Assignment

Use search to find the best person for a task:

```python
# Search for users with specific skills
backend_devs = mcp__whatsapp_monitoring__search_users({
    "query": "backend"
})

frontend_devs = mcp__whatsapp_monitoring__search_users({
    "query": "frontend"
})

# Create tasks assigned to appropriate team members
backend_task = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Implement REST API endpoints",
    "assigned_to": backend_devs["users"][0]["email"] if backend_devs["users"] else None,
    "priority": "High"
})

frontend_task = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Update dashboard UI",
    "assigned_to": frontend_devs["users"][0]["email"] if frontend_devs["users"] else None,
    "priority": "Medium"
})
```

## Example 9: Error Handling

Robust error handling for task creation:

```python
def create_task_safely(task_data):
    """Create task with comprehensive error handling"""
    try:
        result = mcp__whatsapp_monitoring__create_erp_task(task_data)

        if result.get("success"):
            return {
                "status": "success",
                "task_id": result["task_id"],
                "task_url": result["task_url"]
            }

        elif result.get("needs_disambiguation"):
            # Handle disambiguation
            resolution = mcp__whatsapp_monitoring__resolve_user_interactive({
                "query": task_data["assigned_to"]
            })

            # Wait for admin response
            resolved = mcp__whatsapp_monitoring__check_disambiguation({
                "resolution_id": resolution["resolution_id"],
                "wait": True,
                "timeout": 300
            })

            if resolved.get("resolved"):
                # Retry task creation with resolved user
                task_data["assigned_to"] = resolved["email"]
                return create_task_safely(task_data)
            else:
                return {
                    "status": "error",
                    "message": "User disambiguation failed or timed out"
                }

        else:
            return {
                "status": "error",
                "message": result.get("error", "Unknown error")
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# Usage
result = create_task_safely({
    "subject": "Important task",
    "assigned_to": "john",
    "priority": "High"
})

if result["status"] == "success":
    print(f"Task created: {result['task_url']}")
else:
    print(f"Failed: {result['message']}")
```

## Example 10: Integration with Claude Flow Hooks

Use MCP server with claude-flow hooks for coordination:

```python
# Pre-task hook: Validate user exists
def validate_task_assignment(task_data):
    """Validate user assignment before creating task"""
    if "assigned_to" in task_data:
        users = mcp__whatsapp_monitoring__search_users({
            "query": task_data["assigned_to"]
        })

        if users["count"] == 0:
            return False, f"No users found for '{task_data['assigned_to']}'"

        if users["count"] > 3:
            return False, f"Too many matches ({users['count']}), please be more specific"

    return True, "Validation passed"

# Create task with validation
valid, message = validate_task_assignment({
    "subject": "Review code",
    "assigned_to": "john"
})

if valid:
    result = mcp__whatsapp_monitoring__create_erp_task({
        "subject": "Review code",
        "assigned_to": "john",
        "auto_resolve": True
    })
else:
    print(f"Validation failed: {message}")
```

## Example 11: User Preference Learning

Build a system that learns user assignment preferences:

```python
# Track successful assignments
assignment_history = {}

def assign_with_learning(task_type, user_query):
    """Assign tasks based on historical patterns"""
    # Check if we have a preferred user for this task type
    if task_type in assignment_history:
        preferred_user = assignment_history[task_type]
        print(f"Using learned preference: {preferred_user}")
        return preferred_user

    # Search and resolve user
    users = mcp__whatsapp_monitoring__search_users({
        "query": user_query
    })

    if users["count"] == 1:
        assigned_user = users["users"][0]["email"]
        # Remember this assignment
        assignment_history[task_type] = assigned_user
        return assigned_user

    return None

# Usage
assignee = assign_with_learning("code_review", "senior dev")

task = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Code review for feature X",
    "assigned_to": assignee,
    "priority": "High"
})
```

## Example 12: Task Status Monitoring

Check task status after creation:

```python
# Create task
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Deploy to production",
    "priority": "Urgent"
})

# Get task status
if result["success"]:
    status = mcp__whatsapp_monitoring__get_task_status({
        "task_id": result["task_id"]
    })

    print(f"Task URL: {status['task_url']}")
    print(f"View task at: {status['task_url']}")
```

## Advanced Patterns

### Pattern 1: Fuzzy Matching Threshold Tuning

```python
# Test different match thresholds to find optimal value
# This helps determine the right FUZZY_MATCH_THRESHOLD in settings

test_queries = ["john", "dev", "admin"]
thresholds = [70, 80, 90]

for threshold in thresholds:
    # Would need to update FUZZY_MATCH_THRESHOLD in settings
    print(f"\nTesting threshold: {threshold}")

    for query in test_queries:
        users = mcp__whatsapp_monitoring__search_users({"query": query})
        print(f"  {query}: {users['count']} matches")
```

### Pattern 2: Task Templates

```python
# Define task templates for common scenarios
TASK_TEMPLATES = {
    "bug_fix": {
        "subject": "Fix: {description}",
        "priority": "High",
        "assigned_to": "developer"
    },
    "feature": {
        "subject": "Feature: {description}",
        "priority": "Medium",
        "assigned_to": "product_manager"
    },
    "urgent": {
        "subject": "URGENT: {description}",
        "priority": "Urgent",
        "assigned_to": "team_lead"
    }
}

def create_from_template(template_name, description, **kwargs):
    """Create task from template"""
    if template_name not in TASK_TEMPLATES:
        return {"error": f"Unknown template: {template_name}"}

    template = TASK_TEMPLATES[template_name].copy()
    template["subject"] = template["subject"].format(description=description)

    # Override with kwargs
    template.update(kwargs)

    return mcp__whatsapp_monitoring__create_erp_task(template)

# Usage
result = create_from_template(
    "bug_fix",
    "Login page crashes on mobile",
    due_date="2025-10-25"
)
```

## Troubleshooting Examples

### Issue: User not found

```python
# Problem: User doesn't exist
result = mcp__whatsapp_monitoring__create_erp_task({
    "subject": "Test task",
    "assigned_to": "nonexistent_user"
})

# Solution: List users first to verify
users = mcp__whatsapp_monitoring__list_erp_users({"limit": 1000})
print(f"Available users: {len(users['users'])}")

# Search for similar users
similar = mcp__whatsapp_monitoring__search_users({
    "query": "nonexistent"
})
print(f"Similar users: {similar['count']}")
```

### Issue: Disambiguation timeout

```python
# Problem: Admin doesn't respond in time
resolution = mcp__whatsapp_monitoring__resolve_user_interactive({
    "query": "smith"
})

# Solution: Use longer timeout or fall back to auto-resolve
try:
    result = mcp__whatsapp_monitoring__check_disambiguation({
        "resolution_id": resolution["resolution_id"],
        "wait": True,
        "timeout": 300  # 5 minutes
    })
except TimeoutError:
    # Fallback to auto-resolve
    result = mcp__whatsapp_monitoring__create_erp_task({
        "subject": "Task for Smith",
        "assigned_to": "smith",
        "auto_resolve": True  # Auto-select best match
    })
```

## Best Practices

1. **Always use auto_resolve for batch operations**
2. **Validate users exist before critical tasks**
3. **Use exact email addresses when possible**
4. **Implement retry logic for network errors**
5. **Cache user lists to reduce API calls**
6. **Use interactive resolution only when necessary**
7. **Set appropriate timeouts based on urgency**
8. **Log all task creations for audit trail**

## Next Steps

- See `MCP_SERVER.md` for complete API reference
- Check `test_mcp_server.py` for testing examples
- Review ERPNext API documentation for task fields
- Configure WhatsApp MCP for full integration
