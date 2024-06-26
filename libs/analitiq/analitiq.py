import logging
import os
import sys
from pathlib import Path
from analitiq.base.BaseMemory import BaseMemory
from analitiq.llm.BaseLlm import AnalitiqLLM
from analitiq.base.BaseResponse import BaseResponse
from analitiq.utils.general import load_yaml, extract_hints
from analitiq.base.GlobalConfig import GlobalConfig

from analitiq.base.Graph import Graph, Node
from analitiq.base.BaseSession import BaseSession

from analitiq.prompt import (
    HELP_RESPONSE
)

# import langchain
# langchain.debug = True

core_config = load_yaml(Path('analitiq/core_config.yml')) #this is analitiq project.yml
project_config = load_yaml(Path('project.yml')) #this is the users project.yml
sys.path.append("/analitiq")

# Check if the log directory exists
if not os.path.exists(project_config['config']['general']['log_dir']):
    # If it doesn't exist, create it
    os.makedirs(project_config['config']['general']['log_dir'])
print()

logging.basicConfig(
    filename=f"{project_config['config']['general']['log_dir']}/{project_config['config']['general']['latest_run_filename']}"
    ,encoding='utf-8'
    ,filemode='w'
    ,level=logging.INFO
    ,format='%(levelname)s (%(asctime)s): %(message)s (Line: %(lineno)d [%(filename)s])'
    ,datefmt='%d/%m/%Y %I:%M:%S %p'
)

class Analitiq():

    def __init__(self, user_prompt):
        """
        self.prompts is a dictionary that will have 1. original prompt as by user and refined prompt by LLM.
        :param user_prompt:
        """
        self.memory = BaseMemory()
        self.services = GlobalConfig().services
        self.avail_services_str = self.get_available_services_str(self.services)
        self.llm = AnalitiqLLM()
        self.prompts = {'original': user_prompt}
        self.response = BaseResponse(self.__class__.__name__)

    def get_available_services_str(self, avail_services):
        """
        :param avail_services: A dictionary containing the available services. Each service should be represented by a key-value pair, with the key being the name of the service and the value
        * being a dictionary containing the service details.
        :return: A string containing the formatted representation of the available services.

        """
        available_services_list = []

        # Iterate over each item in the Services dictionary
        for name, details in avail_services.items():
            # Determine the appropriate description to use
            description = details['description']
            # Format and add the string to the list
            available_services_list.append(f"{name}: {description}. The input for this tools is {details['inputs']}. The output of this tools is {details['outputs']}.")
            # Join the list into a single string variable, separated by new lines
        available_services_str = "\n".join(available_services_list)

        return available_services_str


    def is_prompt_clear(self, user_prompt, msg_lookback: int = 2):
        """

        :param user_prompt:
        :param msg_lookback: Because the current prompt is already written to chat log, we need to go back 2 steps to get the previous prompt.
        :param feedback: Feedback to the LLM model after failed runs to help the model fix an issue.
        :return:
        """

        try:
            response = self.llm.llm_is_prompt_clear(user_prompt, self.avail_services_str)
        except Exception as e:
            logging.error(f"[Analitiq] Exception: '{e}'. Needs explanation:\n{str(response)}")

        # is LLM is clear with prompt, we return results
        if response.Clear:
            return response

        # Log that the model needs clarification
        logging.info(f"[Analitiq] Prompt not clear: '{user_prompt}'. Needs explanation:\n{str(response)}")

        # we try to get Chat history for more context to the LLM
        try:
            chat_hist = self.get_chat_hist(user_prompt, msg_lookback)
        except Exception as e:
            logging.error(f"[Analitiq] Error retrieving chat history: {e}")
            return response

        # if response is not clear and there is no chat history, we exit with False
        if not chat_hist:
            logging.info(f"[Analitiq] No chat history found.")
            return response

        # if there is chat history, we add it to the prompt to give LLM more context.
        logging.info(f"[Analitiq] Chat history: '{chat_hist}'")
        user_prompt = chat_hist + "\n" + user_prompt
        response = self.llm.llm_is_prompt_clear(user_prompt, self.avail_services_str)

        # Update feedback with the latest exception
        #feedback = f"\nCheck your output and make sure it conforms to instructions! Your previous response created an error:\n{str(e)}"

        return response


    def get_chat_hist(self, user_prompt, msg_lookback: int = 5):
        """
        Gets the chat history for a user prompt.
        This function retrieves recent user prompts from the conversation history,
        specifically those marked with an 'entity' value of 'Human', and within
        the last 5 minutes. It then combines these prompts with the current user
        prompt, if the current prompt is not already present in the history.
        The combined prompt is constructed by concatenating these unique prompts
        into a single string, separated by periods. If the user prompt is the only
        prompt, or if it's the first unique prompt in the specified time frame,
        it is returned as is.
        Note:
        - This function relies on `BaseMemory.get_last_messages_within_minutes` method to fetch
          historical prompts. Ensure `BaseMemory` is properly initialized and configured.
        - This function assumes that the `BaseMemory` method successfully returns a list of
          message dictionaries, each containing at least a 'content' key.
        - The chronological order of prompts in the combined string is determined by the order
          of prompts retrieved from the conversation history, with the current user prompt added last.


        :param user_prompt: The user prompt.
        :param msg_lookback: The number of messages to look back in the chat history. Default is 5.
        :return: The response generated based on the chat history, or None if there is no chat history.
        """

        user_prompt_hist = self.memory.get_last_messages_within_minutes(msg_lookback, 5, 1, 'Human')

        response = None

        if not user_prompt_hist:
            return response

        user_prompt_list = list({message['content'] for message in user_prompt_hist})

        if len(user_prompt_list) > 0:
            user_prompt_w_hist = '\n'.join(user_prompt_list)

            response = self.llm.llm_summ_user_prompts(user_prompt, user_prompt_w_hist)

            logging.info(f"[Prompt][Change From]: {user_prompt_w_hist}\n[Prompt][Change To]: {response}")

        return response


    def run(self, user_prompt):
        """

        :param user_prompt:
        :return:
        """
        session = BaseSession()
        session_uuid = session.get_or_create_session_uuid()

        # First, we check if user typed Help. If so, we can skiop the rest of the logic, for now
        if user_prompt.lower() == 'help':
            return HELP_RESPONSE + '\n'.join([f"{details['name']}: {details['description']}" for details in self.services.values()])

        logging.info(f"\nUser query: {user_prompt}")

        # check if there are user hints in the prompt
        self.prompts['original'], self.prompts['hints'] = extract_hints(user_prompt)

        self.memory.log_human_message(user_prompt)
        self.memory.save_to_file()

        # we now trigger the main forward logic: goal -> tasks -> services/tools -> outcome

        # Step 1 - Is the task clear? IF not and there is no history to fall back on, exit with feedback.
        prompt_clear_response = self.is_prompt_clear(self.prompts['original'])

        if not prompt_clear_response.Clear:
            self.response.set_content(prompt_clear_response.Feedback)
            return {"Analitiq": self.response}

        # add the refined prompts by the model.
        self.prompts['refined'] = prompt_clear_response.Query
        self.prompts['feedback'] = prompt_clear_response.Feedback
        user_prompt = self.prompts['refined']

        logging.info(f"\nRefined prompt context: {self.prompts}")

        selected_services = self.llm.llm_select_services(self.prompts, self.avail_services_str)

        # Convert list of objects into a dictionary where name is the key and description is the value
        selected_services = {service.Action: {'Action': service.Action, 'ActionInput': service.ActionInput, 'Instructions': service.Instructions, 'DependsOn': service.DependsOn} for service in selected_services}

        logging.info(f"\n[Services][Selected]:\n{selected_services}")

        # Building node dependency
        # Check if the list contains exactly one item
        if len(selected_services) == 0:
            self.response.set_content("No services selected.")
            return {"Analitiq": self.response}

        # Initialize the execution graph with the context
        graph = Graph(self.services)

        for service, details in selected_services.items():
            graph.add_node(service, details)

        # if there is only one node, there is no dependency, and we exit
        if len(selected_services) > 1:
            graph.build_service_dependency(selected_services)

        # Now, the graph is ready, and you can execute it
        graph.get_dependency_tree()

        node_outputs = graph.run(self.services)

        return node_outputs

