import os
import google.generativeai as genai
from dotenv import load_dotenv

# It's good practice to load environment variables at the start
load_dotenv()

def invoke_llm(prompt: str) -> str:
    """
    Invokes the Google Gemini model with the given prompt.

    Args:
        prompt: The prompt to send to the language model.

    Returns:
        The model's response text.
    """
    try:
        # Configure the API key from environment variables
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables.")
        
        genai.configure(api_key=api_key)
        
        # Create the model and generate content
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        return response.text
    except Exception as e:
        # Basic error handling
        print(f"An error occurred while calling the LLM: {e}")
        return f"Error: Could not get a response from the LLM. Details: {e}"
