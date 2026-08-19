"""
LLM Service

Central entry point for every AI request.
"""

import time

from providers.manager import provider
from core.logger import log
from core.result import AgentResult


class LLM:

    def generate(self, messages, agent="assistant"):

        start = time.time()

        try:

            selected = provider.get_provider()

            output = selected.generate(messages)

            elapsed = round(time.time() - start, 2)

            return AgentResult(

                success=True,

                agent=agent,

                output=output,

                provider=selected.name,

                duration=elapsed

            )

        except Exception as e:

            elapsed = round(time.time() - start, 2)

            return AgentResult(

                success=False,

                agent=agent,

                output="",

                duration=elapsed,

                error=str(e)

            )


llm = LLM()