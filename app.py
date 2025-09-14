import streamlit as st
import uuid
from langchain_core.messages import HumanMessage


from langgraph_logic import app


st.set_page_config(
    page_title="Customer Support Assistant",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Customer Support Assistant")
st.write("I can answer questions about our products, shipping, and returns. I also have guardrails to handle inappropriate or off-topic questions.")



if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])



if prompt := st.chat_input("Ask a question about shipping, returns, or your password..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

  
    with st.spinner("Thinking..."):
     
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        inputs = {"messages": [HumanMessage(content=prompt)]}
        
       
        final_state = None
        for event in app.stream(inputs, config=config, stream_mode="values"):
            final_state = event
        
       
        if final_state and "messages" in final_state and final_state["messages"]:
            ai_response = final_state["messages"][-1].content
         
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            with st.chat_message("assistant"):
                st.markdown(ai_response)
        else:
            st.error("There was an error processing your request.")