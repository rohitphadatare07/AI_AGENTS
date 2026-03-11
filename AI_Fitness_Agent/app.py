# from smolagents import CodeAgent, DuckDuckGoSearchTool, InferenceClientModel

from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel, ToolCallingAgent, tool
from Gradio_UI import GradioUI

model = LiteLLMModel(
    model_id="ollama/qwen2:1.5b",   # your local model
    api_base="http://localhost:11434"
)


@tool
def convert_lb_to_kg(weight_lb: float) -> float:
    """
    Convert weight from pounds to kilograms.

    Use this tool to convert lb or pounds to kg.

    Args:
        weight_lb: Weight in pounds.

    Returns:
        Converted weight in kilograms.
    """
    weight_in_kg = weight_lb * 0.453592
    return weight_in_kg

@tool
def calculate_bmr(weight_kg: float, height_cm: int, age: int, gender: str) -> float:
    """
    Calculate Basal Metabolic Rate (BMR) based on weight, height, age, and gender.

    IMPORTANT:
    weight must be in kilograms. If the user gives pounds or lb, convert using convert_lb_to_kg tool first.


    Args:
        weight_kg: Weight in kilograms.
        height_cm: Height in centimeters.
        age: Age in years.
        gender: Gender ('male' or 'female').

    Returns:
        The calculated BMR.
    """
    if gender == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return bmr

@tool
def energy_expenditure(bmr: float, activity_level: str) -> str:
    """
    Calculate energy expenditure based on BMR and activity level.
    Use this tool whenever the user asks to calculate energy expenditure.

    Args:
        bmr: Basal Metabolic Rate.
    
        activity_level: One of the following values:
            - Sedentary
            - Lightly Active
            - Moderately Active
            - Very Active
            - Super Active

    Returns:
        Total daily energy expenditure in calories.
    """             
    if activity_level == "Sedentary":
        activity_multiplier = 1.2
    elif activity_level == "Lightly Active":
        activity_multiplier = 1.375
    elif activity_level == "Moderately Active":
        activity_multiplier = 1.55
    elif activity_level == "Very Active":
        activity_multiplier = 1.725
    elif activity_level == "Super Active":
        activity_multiplier = 1.9
    else:
        raise ValueError("Invalid activity level. Please choose from: Sedentary, Lightly Active, Moderately Active, Very Active, Super Active.")

    tdee = bmr * activity_multiplier
    return tdee

agent = CodeAgent(
    tools=[convert_lb_to_kg, calculate_bmr, energy_expenditure],
    model=model,
    instructions="""
    You are a health assistant.

    To calculate energy expenditure follow this workflow:

    1. If weight is given in pounds or lb, first use convert_lb_to_kg.
    2. Then use calculate_bmr.
    3. Then use energy_expenditure.

    Never skip steps.
    The final answer must come from energy_expenditure.
    """
)

# agent.run("What is the capital of France?")

ui = GradioUI(agent)

ui.launch()