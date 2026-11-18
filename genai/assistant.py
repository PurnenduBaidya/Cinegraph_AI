from rich import print
from genai.llm import llm,movie_recommendation_prompt
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage
)

from genai.tools import (
    recommend_similar_movies,
    search_movie_by_title,
    get_movie_details
)

tools = [
    recommend_similar_movies,
    search_movie_by_title,
    get_movie_details
]

llm_with_tools = llm.bind_tools(tools)

conversation_history = []

tools_by_name = {
    tool.name: tool
    for tool in tools
}


def run_assistant(user_query: str, max_iterations: int = 5):

    if not conversation_history:

        messages = movie_recommendation_prompt.format_messages(
            user_query=user_query
        )

        conversation_history.extend(messages)

    else:

        conversation_history.append(
            HumanMessage(content=user_query)
        )

    for iteration in range(max_iterations):

        try:

            response = llm_with_tools.invoke(conversation_history)

            # Store AI response in conversation history
            conversation_history.append(response)

            # If no tool call, return final answer
            if not response.tool_calls:

                return response.content

            for tool_call in response.tool_calls:

                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                print(f"\n[bold cyan]Calling tool:[/bold cyan] {tool_name}")
                print(f"Arguments: {tool_args}")

                selected_tool = tools_by_name.get(tool_name)

                if selected_tool is None:

                    tool_result = f"Error: Tool '{tool_name}' not found."

                else:

                    try:

                        tool_result = selected_tool.invoke(tool_args)

                    except Exception as error:

                        print(f"[bold red]Tool Error:[/bold red] {error}")

                        tool_result = (
                            f"Tool execution failed: {str(error)}"
                        )

                # print("\n[bold yellow]Tool Result:[/bold yellow]")
                # print(tool_result)

                # Store tool result in conversation history
                conversation_history.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_id
                    )
                )

        except Exception as error:

            print(f"\n[bold red]Assistant Error:[/bold red] {error}")

            return (
                "Sorry, something went wrong while "
                "processing your request."
            )

    return (
        "I couldn't complete your request within the maximum "
        "number of tool-calling iterations."
    )

