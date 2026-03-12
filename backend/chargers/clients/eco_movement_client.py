import os
from dotenv import load_dotenv

load_dotenv()

API_KEYS = {
    'blink': os.environ['ECO_MOVEMENT_BLINK_API_KEY'], 
    'bp': os.environ['ECO_MOVEMENT_BP_API_KEY'],
    'ionity': os.environ['ECO_MOVEMENT_IONITY_API_KEY'],
    'shell': os.environ['ECO_MOVEMENT_SHELL_API_KEY']
}