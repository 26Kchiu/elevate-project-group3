"""WorkWeek HCM MCP Server configuration and reference.

The live WorkWeek HCM MCP server is hosted at:
    https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/

Supported MCP Tools:
- get_current_employee_id: Resolves active session's employee ID
- get_employee_balances: Fetches leave balances (Vacation and Sick)
- get_personal_info: Fetches contact details (Address and Phone)
- get_leave_requests: Retrieves history of time off requests
- request_time_off: Submits a time off request
- update_personal_info: Updates address and phone number
- cancel_leave_request: Cancels a leave request and refunds days
"""

import os

WORKWEEK_MCP_URL = os.environ.get("WORKWEEK_MCP_URL", "https://mock-saas.aishprabhat.demo.altostrat.com/work-week/mcp/")
WORKWEEK_MCP_TOKEN = os.environ.get("WORKWEEK_MCP_TOKEN", "")
