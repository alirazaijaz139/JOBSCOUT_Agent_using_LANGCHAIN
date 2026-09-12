import streamlit as st
from pypdf import PdfReader
from docx import Document

from RAG.loader import split_text
from RAG.embeddings import get_embeddings
from RAG.vectorstore import create_vectorstore
from RAG.retrieval import get_retriever

from langchain_google_genai import ChatGoogleGenerativeAI
from Tools.job_search_tool import recommend_jobs_from_cv

from dotenv import load_dotenv
load_dotenv()

from agent import run_agent


# =========================
# JobScout AI
# =========================

st.title("JobScout AI")
st.write("Your AI Career Assistant")


# =========================
# CV Upload
# =========================

uploaded_file = st.file_uploader(
    "Upload your CV",
    type=["pdf", "docx"]
)


if uploaded_file is not None:

    # =========================
    # Extract CV Text
    # =========================

    if uploaded_file.name.endswith(".pdf"):

        reader = PdfReader(uploaded_file)

        text = ""

        for page in reader.pages:
            text += page.extract_text()

    elif uploaded_file.name.endswith(".docx"):

        document = Document(uploaded_file)

        text = ""

        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"


    # =========================
    # Save CV Text
    # =========================

    st.session_state["cv_text"] = text


    # =========================
    # Display CV Content
    # =========================

    st.subheader("CV Content")

    st.write(text)


    # =========================
    # Split CV into Chunks
    # =========================

    chunks = split_text(text)

    st.subheader("Number of Chunks")

    st.write(len(chunks))


    st.subheader("First Chunk")

    st.write(chunks[0].page_content)


    # =========================
    # Create Embeddings
    # =========================

    embeddings = get_embeddings()


    # Embedding test

    vector = embeddings.embed_query(
        "What are the major areas of artificial intelligence?"
    )


    st.subheader("Embedding Test")

    st.write(
        "Embedding dimensions:",
        len(vector)
    )

    st.write(
        "First 10 values:",
        vector[:10]
    )


    # =========================
    # Create Vector Store
    # =========================

    vectorstore = create_vectorstore(
        chunks,
        embeddings
    )


    st.success(
        "Documents stored in Chroma Vector Database!"
    )


    # =========================
    # Create Retriever
    # =========================

    retriever = get_retriever(vectorstore)


    # =========================
    # Ask Questions About CV
    # =========================

    question = st.chat_input(
        "Ask something about your CV"
    )


    if question:

        docs = retriever.invoke(question)


        st.subheader("Retrieved Documents")


        for doc in docs:

            st.write(doc.page_content)


        # =========================
        # Gemini LLM
        # =========================

        llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0
        )


        context = "\n\n".join(
            doc.page_content
            for doc in docs
        )


        prompt = f"""
Answer the question using only the context below.

Context:
{context}

Question:
{question}
"""


        response = llm.invoke(prompt)


        st.subheader("AI Answer")


        if isinstance(response.content, list):

            answer = "\n".join(
                item.get("text", "")
                for item in response.content
                if isinstance(item, dict)
                and item.get("type") == "text"
            )

        else:

            answer = response.content


        st.write(answer)

        st.divider()


# ==================================================
# Job Search Agent
# ==================================================

st.header("🔎 Job Search Agent")


job_question = st.text_input(
    "Search for jobs",
    placeholder="e.g. Find Python Developer jobs"
)


if st.button("Search Jobs"):

    if job_question:

        with st.spinner("Searching for jobs..."):

            cv_text = st.session_state.get("cv_text", "")

            answer = run_agent(
                job_question,
                cv_text
            )


        st.subheader("🤖 JobScout AI")


        st.write(answer)


    else:

        st.warning(
            "Please enter a job search question."
        )
        
        
    st.divider()

st.header("🎯 Recommended Jobs For You")

if st.button("Recommend Jobs For Me"):

    cv_text = st.session_state.get("cv_text", "")

    if cv_text:

        with st.spinner("Finding jobs based on your CV..."):

            recommendations = recommend_jobs_from_cv.invoke(
                cv_text
            )

        st.subheader("🤖 JobScout AI Recommendations")

        st.write(recommendations)

    else:

        st.warning(
            "Please upload your CV first."
        )