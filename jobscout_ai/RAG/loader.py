from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )

    chunks = splitter.create_documents([text])

    return chunks