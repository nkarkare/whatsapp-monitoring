#!/usr/bin/env python3
"""
WhatsApp Group Discovery Helper

This script helps you discover WhatsApp group JIDs for configuration.
Run this script to list all your groups and get copy-paste ready config values.
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# Add project to path
project_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_dir))

# Check if MCP is available
try:
    from mcp import ClientSession, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  Warning: MCP not installed. Install with: pip install mcp")

async def list_whatsapp_groups():
    """List all WhatsApp groups using MCP server"""
    if not MCP_AVAILABLE:
        print("\n❌ Error: MCP library not available")
        print("Install dependencies: pip install -r requirements.txt")
        return []

    try:
        print("🔍 Connecting to WhatsApp MCP server...")

        # Initialize WhatsApp MCP client
        server_params = StdioServerParameters(
            command="npx",
            args=["--yes", "@raaedkabir/whatsapp-mcp-server"],
            env=os.environ.copy()
        )

        async with ClientSession(server_params) as session:
            print("✓ Connected successfully\n")
            print("📱 Fetching your WhatsApp chats...\n")

            # List all chats
            result = await session.call_tool(
                "list_chats",
                {
                    "limit": 100,
                    "include_last_message": False
                }
            )

            if not result or not result.content:
                print("❌ No response from WhatsApp MCP server")
                return []

            # Parse response
            chats_data = None
            for content in result.content:
                if hasattr(content, 'text'):
                    chats_data = json.loads(content.text)
                    break

            if not chats_data:
                print("❌ Could not parse response")
                return []

            chats = chats_data.get("chats", [])

            # Filter for groups only (JIDs ending with @g.us)
            groups = [chat for chat in chats if chat.get("jid", "").endswith("@g.us")]

            return groups

    except Exception as e:
        print(f"\n❌ Error connecting to WhatsApp MCP: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure WhatsApp Bridge is running")
        print("2. Make sure WhatsApp MCP server is installed:")
        print("   npx @raaedkabir/whatsapp-mcp-server")
        print("3. Check your WhatsApp connection")
        return []

def display_groups(groups):
    """Display groups in a user-friendly format"""
    if not groups:
        print("\n⚠️  No groups found!")
        print("\nPossible reasons:")
        print("1. You're not part of any groups")
        print("2. WhatsApp Bridge hasn't synced yet")
        print("3. Connection issue with WhatsApp")
        return

    print("=" * 70)
    print(f"📊 Found {len(groups)} WhatsApp Groups")
    print("=" * 70)
    print()

    # Display each group
    for idx, group in enumerate(groups, 1):
        name = group.get("name", "Unnamed Group")
        jid = group.get("jid", "")

        print(f"{idx}. {name}")
        print(f"   JID: '{jid}'")
        print()

    # Generate copy-paste config
    print("=" * 70)
    print("📋 Copy-Paste Configuration Examples")
    print("=" * 70)
    print()

    # All groups for daily summary
    all_jids = "','".join([g.get("jid", "") for g in groups])
    print("🌅 For Daily Summaries (all groups):")
    print(f"DAILY_SUMMARY_GROUPS='{all_jids}'")
    print()

    # All groups for keyword monitoring
    print("🔍 For Keyword Monitoring (all groups):")
    print(f"MONITORED_GROUPS='{all_jids}'")
    print()

    # First 3 groups as example
    if len(groups) >= 3:
        sample_jids = "','".join([g.get("jid", "") for g in groups[:3]])
        print("📝 Example with first 3 groups only:")
        print(f"DAILY_SUMMARY_GROUPS='{sample_jids}'")
        print()

    # Monitor all groups option
    print("🌐 To monitor ALL groups (alternative):")
    print("MONITORED_GROUPS='all'")
    print()

    print("=" * 70)
    print("💡 Next Steps:")
    print("=" * 70)
    print("1. Copy the configuration line you want")
    print("2. Edit config/settings.env (NOT settings.template.env)")
    print("3. Paste the configuration")
    print("4. Set DAILY_SUMMARY_ENABLED=true or KEYWORD_MONITORING_ENABLED=true")
    print("5. Configure recipient phone numbers")
    print("6. Restart the monitor: ./run_monitor.sh restart")
    print()

async def main():
    """Main function"""
    print("\n🔧 WhatsApp Group Discovery Tool")
    print("=" * 70)
    print()

    groups = await list_whatsapp_groups()
    display_groups(groups)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
