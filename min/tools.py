# tool.py
import os
import re
from typing import Dict, List, Any, Optional, Union
from typing_extensions import Annotated
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from dotenv import load_dotenv

# sympy 임포트
from sympy import sympify, SympifyError
from sympy.core.numbers import Integer, Float, Number
from sympy.parsing.latex import parse_latex

# 사용자 정의 모듈 임포트
from db import db, engine, table_info
from state import State, create_empty_user_memo, memo_set_budget, memo_set_wedding_date

# 환경 변수 로드
load_dotenv()

# 웹 검색 도구 초기화
tavily_tool = TavilySearchResults(max_results=3)

# 유용한 유틸리티 함수
def _sanitize_input(text: str) -> str:
    """Helper function to remove SQL-injection-prone characters."""
    return re.sub(r"[\"\';`]+", "", text)

# --- 도구 정의 ---

def web_search_tool(query: Annotated[str, "Query to search the web for."]) -> str:
    """
    Search the web for information using a search engine. Useful for finding general information,
    trending topics, or details not present in the internal database.

    Args:
        query (str): The search query.
    Returns:
        str: A summary of the search results.
    """
    return tavily_tool.invoke({"query": query})

def calculator_tool(expression: Annotated[str, "The mathematical expression to evaluate, e.g., '2 + 2' or '(5 * 10) / 2'."]) -> Union[float, int, str]:
    """
    Perform a mathematical calculation. Use this for all arithmetic operations.
    Supports basic operations like addition, subtraction, multiplication, division, and parentheses.
    This tool uses a secure math library to prevent code injection.

    Args:
        expression (str): The mathematical expression to calculate.
    Returns:
        Union[float, int, str]: The result of the calculation. Returns an error message if the expression is invalid.
    """
    try:
        # Check for potentially malicious patterns
        # Although sympify is safer than eval, this adds an extra layer of defense
        if re.search(r'[a-zA-Z_]', expression):
            return "Error: Invalid characters in the expression. Only numbers and basic operators are allowed."

        expr = sympify(expression)
        
        # Evaluate the expression to a numerical value
        result = expr.evalf()
        
        # Format the result to avoid scientific notation for simple integers/floats
        if isinstance(result, (Integer, Float)):
            if result.is_integer:
                return int(result)
            else:
                return float(result)
        
        return str(result)
        
    except SympifyError as e:
        return f"Error evaluating expression: {e}. Please ensure the expression is a valid mathematical format."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def db_query_tool(query: Annotated[str, "The SQL query to execute on the database. It should be a SELECT statement."]) -> str:
    """
    Executes a read-only SQL query on the wedding hall, studio, wedding dress, or makeup database tables.
    Use this to retrieve information like names, prices, locations, or features of vendors.
    IMPORTANT: ONLY use SELECT statements. NEVER use DELETE, INSERT, or UPDATE.

    Args:
        query (str): The SQL query string.
    Returns:
        str: The results of the query or an error message.
    """
    try:
        if not query.lower().strip().startswith("select"):
            return "Error: Only SELECT queries are allowed."
        
        with engine.connect() as connection:
            result = connection.execute(query).fetchall()
            return str(result)
    except Exception as e:
        return f"Database query failed: {str(e)}"

def user_db_update_tool(
    state: State,
    user_id: Annotated[str, "The unique identifier of the user."],
    field: Annotated[str, "The field to update in the user's profile, e.g., 'total_budget_manwon' or 'wedding_date'."],
    value: Annotated[Any, "The new value for the field."]
) -> str:
    """
    Update a specific field in the user's long-term memory (memo) in the database.
    This is used to save or change user-provided information such as budget, wedding date, etc.
    The 'state' and 'user_id' arguments are passed implicitly by the framework.

    Args:
        state (State): The current state of the conversation.
        user_id (str): The unique ID of the user.
        field (str): The key of the field to update.
        value (Any): The new value for the field.

    Returns:
        str: A confirmation message indicating the update status.
    """
    try:
        if field == "total_budget_manwon":
            memo_set_budget(state, value)
        elif field == "wedding_date":
            memo_set_wedding_date(state, value)
        else:
            return f"Error: The field '{field}' is not supported for updates."

        return f"Successfully updated user profile for field: {field} with value: {value}"
    except Exception as e:
        return f"Failed to update user profile: {str(e)}"