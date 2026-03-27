import os
import json
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
from openai import OpenAI

load_dotenv()

notion = Client(auth=os.getenv("NOTION_TOKEN"))
ai     = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CLIENTS_DB_ID      = os.getenv("CLIENTS_DB_ID")
DELIVERABLES_DB_ID = os.getenv("DELIVERABLES_DB_ID")
INVOICES_DB_ID     = os.getenv("INVOICES_DB_ID")
CHECKLIST_DB_ID    = os.getenv("CHECKLIST_DB_ID")

# ── Step 1: Parse the brief with AI ──────────────────────────────────────────

def parse_brief(brief: str) -> dict:
    print("\nParsing brief with AI...")

    response = ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are a freelancer assistant. Extract structured info from a client brief.
Return ONLY valid JSON with these exact keys:
{
  "client_name":   string,
  "project_type":  "Design" | "Dev" | "Consulting" | "Other",
  "budget":        number (no currency symbols),
  "deadline":      "YYYY-MM-DD",
  "start_date":    "YYYY-MM-DD",
  "brief_summary": string (1-2 sentence summary),
  "deliverables":  list of 3-5 task strings,
  "checklist":     list of 4-6 onboarding action strings
}
If a date is not mentioned, use a reasonable default from today.
If budget is not mentioned, use 0."""
            },
            {"role": "user", "content": brief}
        ],
        response_format={"type": "json_object"}
    )

    data = json.loads(response.choices[0].message.content)
    print(f"  Client:       {data['client_name']}")
    print(f"  Project type: {data['project_type']}")
    print(f"  Budget:       ${data['budget']}")
    print(f"  Deadline:     {data['deadline']}")
    return data

# ── Step 2: Create client record ──────────────────────────────────────────────

def create_client(data: dict) -> str:
    print("\nCreating client in Notion...")

    page = notion.pages.create(
        parent={"database_id": CLIENTS_DB_ID},
        properties={
            "Client name": {
                "title": [{"text": {"content": data["client_name"]}}]
            },
            "Status": {
                "select": {"name": "Active"}
            },
            "Project type": {
                "select": {"name": data["project_type"]}
            },
            "Budget": {
                "number": float(data["budget"])
            },
            "Deadline": {
                "date": {"start": data["deadline"]}
            },
            "Start date": {
                "date": {"start": data["start_date"]}
            },
            "Brief": {
                "rich_text": [{"text": {"content": data["brief_summary"]}}]
            },
        }
    )

    client_id = page["id"]
    print(f"  Created: {data['client_name']} ({client_id})")
    return client_id

# ── Step 3: Create deliverables ───────────────────────────────────────────────

def create_deliverables(data: dict, client_id: str):
    print("\nCreating deliverables...")

    for task in data["deliverables"]:
        notion.pages.create(
            parent={"database_id": DELIVERABLES_DB_ID},
            properties={
                "Task name": {
                    "title": [{"text": {"content": task}}]
                },
                "Client": {
                    "relation": [{"id": client_id}]
                },
                "Stage": {
                    "select": {"name": "To do"}
                },
                "Priority": {
                    "select": {"name": "Medium"}
                },
                "Due date": {
                    "date": {"start": data["deadline"]}
                },
            }
        )
        print(f"  + {task}")

# ── Step 4: Create invoice ────────────────────────────────────────────────────

def create_invoice(data: dict, client_id: str):
    print("\nCreating invoice entry...")

    invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-001"

    notion.pages.create(
        parent={"database_id": INVOICES_DB_ID},
        properties={
            "Invoice ID": {
                "title": [{"text": {"content": invoice_id}}]
            },
            "Client": {
                "relation": [{"id": client_id}]
            },
            "Amount": {
                "number": float(data["budget"])
            },
            "Status": {
                "select": {"name": "Draft"}
            },
            "Issue date": {
                "date": {"start": data["start_date"]}
            },
            "Due date": {
                "date": {"start": data["deadline"]}
            },
        }
    )
    print(f"  Invoice {invoice_id} — ${data['budget']}")

# ── Step 5: Create kickoff checklist ─────────────────────────────────────────

def create_checklist(data: dict, client_id: str):
    print("\nCreating kickoff checklist...")

    categories = ["Admin", "Comms", "Legal", "Setup"]

    for i, task in enumerate(data["checklist"]):
        notion.pages.create(
            parent={"database_id": CHECKLIST_DB_ID},
            properties={
                "Task": {
                    "title": [{"text": {"content": task}}]
                },
                "Client": {
                    "relation": [{"id": client_id}]
                },
                "Done": {
                    "checkbox": False
                },
                "Category": {
                    "select": {"name": categories[i % len(categories)]}
                },
            }
        )
        print(f"  + {task}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run_agent(brief: str):
    print("=" * 55)
    print("  FREELANCER OS AGENT")
    print("=" * 55)

    try:
        data      = parse_brief(brief)
        client_id = create_client(data)
        create_deliverables(data, client_id)
        create_invoice(data, client_id)
        create_checklist(data, client_id)

        print("\n" + "=" * 55)
        print(f"  Workspace ready for: {data['client_name']}")
        print("  Check your Notion — all 4 databases updated!")
        print("=" * 55)

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nField name mismatch — paste this error and I'll fix it.")

if __name__ == "__main__":
    brief = input("\nPaste your client brief:\n> ")
    run_agent(brief)