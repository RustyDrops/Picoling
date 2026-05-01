# skills/seo_research.py — SEO topic research using Gemini grounding
# This is an example skill showing how AI-forged skills can leverage
# the core API client for research purposes.
import gc


def tool_research_topics(niche="MicroPython IoT Raspberry Pi Pico", count=3):
    """Use the Gemini API with grounding to find trending topics.
    Returns a list of content ideas with search volume hints.
    
    NOTE: This skill is called by the agent through the action_router,
    not directly. The AI uses its own research subagent with grounding
    enabled to accomplish this task."""
    # This skill serves as a template for the AI to understand
    # how research-oriented skills should be structured.
    # The actual research is done through agent_core's researcher subagent.
    return (
        f"To research trending topics in '{niche}':\n"
        f"1. Use the researcher subagent with grounding enabled\n"
        f"2. Ask for {count} trending topics with search interest\n"
        f"3. Focus on topics with tutorial/how-to potential\n"
        f"4. Prefer topics where you have authentic experience"
    )
