import sys
import os
from pathlib import Path

# Add the project root to sys.path so we can import modules if needed,
# though here we might just read the file directly as per instructions.
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def load_prompt(prompt_name: str) -> str:
    # Mimic the logic in src/agents/nodes.py
    # src/agents/nodes.py uses Path(__file__).parent.parent / "prompts"
    # referencing from src/agents/nodes.py -> src/prompts
    
    # Here we are in tests/manual_test_supervisor_prompt.py
    # We want to access src/prompts/supervisor.txt
    base_path = project_root / "src" / "prompts"
    prompt_path = base_path / f"{prompt_name}.txt"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    print("--- Loading Supervisor Prompt Template ---")
    try:
        template = load_prompt("supervisor")
    except Exception as e:
        print(f"Error loading prompt: {e}")
        return

    print("--- Formatting with Dummy Data ---")
    dummy_task = "Test Task"
    dummy_structure = "Test Structure\n- Chapter 1\n- Chapter 2"
    
    formatted_prompt = template.format(
        task=dummy_task,
        document_structure=dummy_structure
    )
    
    print("\n--- Formatted Prompt Content ---")
    print(formatted_prompt)
    print("\n--- Verification ---")
    
    tiers_found = []
    if "Tier 1" in formatted_prompt:
        tiers_found.append("Tier 1")
    if "Tier 2" in formatted_prompt:
        tiers_found.append("Tier 2")
    if "Tier 3" in formatted_prompt:
        tiers_found.append("Tier 3")
        
    print(f"Tiers found: {', '.join(tiers_found)}")
    
    if len(tiers_found) == 3:
        print("SUCCESS: All 3 Tiers are present in the prompt.")
    else:
        print(f"FAILURE: Missing tiers. Found: {tiers_found}")

if __name__ == "__main__":
    main()
