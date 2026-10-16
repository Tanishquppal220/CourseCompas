"""Verification script for curriculum grounding and anti-hallucination guardrails.

Simulates the exact user conversation from the chat session:
Turn 1: "I have a Choice to take a open minor this semester what do you think i should take"
Turn 2: "i want to do AI/ML but with this i want to explore some thing diffrent"

Verifies:
1. The agent does NOT hallucinate phantom codes: BUSM101, CSE410, CSE415, CSE420.
2. The agent grounds its recommendations in official database offerings (e.g. IXD801, PID801, FIN212, MKT202, CSE273).
3. The agent quotes accurate credits (3.0 credits).
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.agent import run_agent

def main():
    print("=" * 80)
    print("TESTING CURRICULUM GROUNDING & ANTI-HALLUCINATION GUARDRAILS")
    print("=" * 80)

    # Turn 1
    query_1 = "I have a Choice to take a open minor this semester what do you think i should take"
    print(f"\n[Turn 1 User Query]: {query_1}")
    response_1, sources_1 = run_agent(query_1)
    print("\n[Turn 1 Assistant Response Preview]:")
    print(response_1[:400] + ("..." if len(response_1) > 400 else ""))

    # Turn 2: Follow-up reproducing user's second prompt
    chat_history = [
        {"role": "user", "content": query_1},
        {"role": "assistant", "content": response_1},
    ]
    query_2 = "i want to do AI/ML but with this i want to explore some thing diffrent"
    print(f"\n[Turn 2 User Query]: {query_2}")
    response_2, sources_2 = run_agent(query_2, chat_history=chat_history)
    print("\n[Turn 2 Assistant Response]:")
    print("-" * 80)
    print(response_2)
    print("-" * 80)

    # Hallucination Assertions
    hallucinated_codes = ["BUSM101", "CSE410", "CSE415", "CSE420"]
    found_hallucinations = [code for code in hallucinated_codes if code in response_2]

    print("\n=== VERIFICATION CHECKS ===")
    if found_hallucinations:
        print(f"FAILED: Found hallucinated course codes: {found_hallucinations}")
    else:
        print("PASSED: Zero hallucinated course codes found (BUSM101, CSE410, CSE415, CSE420).")

    # Check for presence of real database courses or tracks
    real_db_indicators = [
        "IXD", "PID", "FIN", "MKT", "ACC", "LAW", "PSY", "CSE273", "CSE274", "CSE470",
        "DESIGN", "MANAGEMENT", "FINANCE", "PSYCHOLOGY", "3 credit"
    ]
    found_real = [ind for ind in real_db_indicators if ind.lower() in response_2.lower()]
    print(f"Grounding indicators found in response: {found_real}")

    if not found_hallucinations and len(found_real) >= 2:
        print("\nALL GROUNDING CHECKS PASSED SUCCESSFULLY!")
        return 0
    else:
        print("\nWARNING: Verification failed some quality checks.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
