from ai_agents.crew import AiAgents

def run():
    inputs = {}

    AiAgents().crew().kickoff(inputs=inputs)

run()