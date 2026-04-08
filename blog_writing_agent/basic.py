
from __future__ import annotations
import os
import operator
from langgraph.graph import StateGraph,START,END,MessagesState
from langchain_groq import ChatGroq
from langgraph.types import Send
from pydantic import BaseModel,Field
from typing import List,Annotated
from langchain_core.messages import HumanMessage,SystemMessage,AIMessage
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

model=ChatGroq(model="openai/gpt-oss-120b",temperature=0.2,api_key=os.getenv("GROQ_API_KEY"))

class Task(BaseModel):
    id:int=Field(description="id of the task")
    title:str=Field(description="title of the task")
    brief:str=Field(description="brief description of the task")

class Plan(BaseModel):
    blog_title:str=Field(description="title of the blog")
    tasks:list[Task]=Field(description="list of tasks to accomplish the blog writing")

class Blogstate(MessagesState):
    title:str=Field(description="title of the blog")
    plan:Plan
    section:Annotated[List[str],operator.add]=Field(description="list of sections in the blog")
    final:str=Field(description="final blog content")

def orchetstator(state:Blogstate)->dict:

    plan=model.with_structured_output(Plan).invoke([
        SystemMessage(content="Create a blog plan with 5–7 sections for the following topic"),
        HumanMessage(content=state["title"])
    ])

    return {
        "plan":plan
    }

def fanout(state:Blogstate):
    return [Send("worker",{"task":task,"topic":state['title'],"plan":state['plan']}) for task in state['plan'].tasks]

def worker(payload:dict)->dict:
    task=payload['task']
    topic=payload['topic']
    plan=payload['plan']

    blog_title=plan.blog_title

    section_content = model.invoke([
        SystemMessage(content="Write one clean Markdown section"),
        HumanMessage(
            content=
            f"Blog: {blog_title}\n"
            f"Topic: {topic}\n\n"
            f"Section: {task.title}\n"
            f"Brief: {task.brief}\n\n"
            "Return only the section content in Markdown."
        )
    ]).content.strip()

    return {
        "section":[section_content]
        }

def reducer(state:Blogstate)->dict:

    title=state['title']
    body="\n\n".join(state['section'])

    final_md = f'# {title}\n\n{body}'

    filename=title.lower().replace(" ","_")+".md"
    output_path=Path(filename)
    output_path.write_text(final_md,encoding="utf-8")

    return {
        "final":final_md
    }


builder=StateGraph(Blogstate)
builder.add_node("orchestrator",orchetstator)
builder.add_node("worker",worker)
builder.add_node("reducer",reducer)
builder.add_edge(START,"orchestrator")
builder.add_conditional_edges("orchestrator",fanout,["worker"])
builder.add_edge("worker","reducer")
builder.add_edge("reducer",END)
graph=builder.compile()

result=graph.invoke({"title":"Ai in Education","section":[]})

print(result)



