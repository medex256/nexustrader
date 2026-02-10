import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def invoke_llm(prompt: str, max_retries: int = 3) -> str:
    """
    Invokes the LLM with the given prompt using Google Gemini.
    Includes retry logic for rate limit errors.

    Args:
        prompt: The prompt to send to the language model.
        max_retries: Maximum number of retry attempts for rate limits (default: 3)

    Returns:
        The model's response text.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Error: GOOGLE_API_KEY not found in environment variables."
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    # Configure generation with temperature for consistency
    generation_config = genai.types.GenerationConfig(
        temperature=0.7,  # Balance creativity and consistency
    )
    
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt, generation_config=generation_config)
            
            # Check if response has valid text
            if hasattr(response, 'text') and response.text:
                return response.text
            else:
                # Handle cases where response.text is not available
                print(f"Warning: Response has no valid text. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
                return "Error: The model returned an empty response. Please try again."
                
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a rate limit error (429)
            if "429" in error_msg or "Quota exceeded" in error_msg or "rate" in error_msg.lower():
                if attempt < max_retries:
                    # Extract retry delay from error message if available
                    wait_time = 10  # Default wait time
                    if "retry in" in error_msg.lower():
                        try:
                            # Try to extract the wait time from error message
                            import re
                            match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                            if match:
                                wait_time = float(match.group(1)) + 1  # Add 1 second buffer
                        except:
                            pass
                    
                    print(f"[RATE LIMIT] Attempt {attempt + 1}/{max_retries + 1} failed. Waiting {wait_time:.0f}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[RATE LIMIT] Max retries reached. Error: {e}")
                    return f"Error: Rate limit exceeded after {max_retries} retries. Please upgrade API plan or wait before retrying."
            else:
                # Non-rate-limit error
                print(f"An error occurred while calling the LLM: {e}")
                return f"Error: Could not get a response from the LLM. Details: {e}"
    
    return "Error: Max retries exceeded."
