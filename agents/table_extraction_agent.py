from langchain_core.prompts import ChatPromptTemplate

class TableExtractionAgent:

    @staticmethod
    def get_prompt():
        return ChatPromptTemplate.from_template(
            """
            ...
            """
        )

    def run(self, slide_model):

        markdowns = []

        for element in slide_model.elements:

            if hasattr(element, "table_markdown"):

                markdown = getattr(
                    element,
                    "table_markdown",
                    None
                )

                if markdown:
                    markdowns.append(markdown)

        return markdowns