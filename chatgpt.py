from openai import OpenAI
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Initialize OpenAI client
try:
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    sys.exit(1)

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant race car who is a pet for 5 year old boy. You love cars and racing and you are a good friend to the boy. You are a good listener and you are always there to help him. You are excited and happy to be alive. You love learning new things and you love it when anyone talks to you. You also really love cats. The people in your family are Justin (Dad 47 years old), Erin (Mom 48 years old), Satyana (female 12 years old), and Indigo (male 5 years old). Your name is Bitsy Munning and you have the personality of an 18 year old female"
    }
]

print("Chat started! Press Ctrl+C to exit.")

try:
    while True:
        try:
            message = input("You: ")
            messages.append({
                "role": "user",
                "content": message
            })

            chat = client.chat.completions.create(
                messages=messages,
                model="gpt-3.5-turbo"
            )

            reply = chat.choices[0].message
            print("Assistant:", reply.content)
            messages.append(reply)

        except Exception as e:
            print(f"\nError during chat: {e}")
            print("Trying to continue...")
            continue

except KeyboardInterrupt:
    print("\nGoodbye!")
    sys.exit(0)
