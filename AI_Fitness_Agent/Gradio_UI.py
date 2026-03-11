import gradio as gr


class GradioUI:
    def __init__(self, agent):
        self.agent = agent

    def chat(self, message, history):
        """
        Function that sends user input to the agent
        and returns the response
        """
        try:
            response = self.agent.run(message)
            return response
        except Exception as e:
            return f"Error: {str(e)}"

    def launch(self):
        with gr.Blocks() as demo:

            gr.Markdown("# 🤖 AI Agent")

            chatbot = gr.ChatInterface(
                fn=self.chat,
                title="Agent Chat",
                description="Ask anything to the AI agent",
            )

        demo.launch()