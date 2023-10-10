<!---
Notes on what AIConsole is and what it can do.
-->

# Notes on what AIConsole is and what it can do.

AIConsole can be used as a personal assistant in your various projects.

* AIConsole allows you to build your own AI-Powered, domain specific, multi-agent personal assistant
* AIConsole offers you the ability to add or edit agents and materials. The more you spend time on it, the better it gets.
* AIConsole can be run locally on a user machine
* It can be used to build domain tools
* AI Agents in AIConsole are built in a way that it conserves AI thinking power (context/tokens) so when it executes a complex task it can only use the information (materials and agent speciality) that is needed for that specific subtask.
* AIConsole has a web interface which makes it easy to operate
* AIConsole can execute any task that is doable in python as it generates code and runs it on the fly, this makes it super easy for it to perform tasks like getting your calendar info or sending emails.
* AIConsole does not need you to know coding in order to do that, it executes that code under the hood (but you can still view it).
* AIConsole has multiple agents, all of them having different chracteristics (system prompt) and mode of operation (normal or code execution).
* AIConsole agents will be able to talk to each other and invoke each other (pending, not yet done)
* You can edit and add your own agents, they are in ./agents directory in the directory you run the aiconsole in
* You can provide materials to the agents, those are pieces of information that the agents will select and use during their work, those are (but not limited to): general information about yourself, infromation on how to 
erform a given task like writing a linkedin post, information how to access a given API, information about service offering of your company etc.
* As you add materials and agents this tool grows with power with time. So the more time you spend on it the better it gets. If it does not know how to do a given task you can teach it.
* When you update your installation of aiconsole, make sure to start a fresh project or delete ./materials and ./agents directories in order to get new versions of them with updated materials and agents.
* When you edit a material, it immediatelly gets reloaded and is available in your current conversation
* Create .md files in ./materials directory in the following format:
```md
<!---
Description of when this material should be used?
-->

# Title of the material

Actual content of a material
```

Files are monitored and automatically loaded, then used as context. You can keep there API materials, login information, prompts and other contextual information.

You can see examples of materials i ./materials directory

* You can go back to previous commands using up arrow
* All chats histories are saved in ./.aic/history
* AIConsole is open source, link to repo: https://github.com/10clouds/aiconsole
* 10Clouds (10clouds.com) is developing custom integrations for it, if you need one feel free to contact us.
* Each directory you run it in is your new project directory
* How to run aiconsole:

```shell
pip install --upgrade aiconsole --pre
cd your_project_dir
export OPENAI_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
aiconsole
```

aiconsole will create a bunch of working files like standard materials and agents

* You have full control how you use the context window of GPT-4, you can delete and edit past messages
* Uses OpenAI GPT-4 internally for all operations, but will be expanded with ability to use open source models. It accesses it through an API.

* Examples of what you can do with AIConsole:
1. Assuming you have description of your company services among your materials, a second material containing top clients and a module to access company org structure (or a text material containing it) - write an email containing a poem about usage of my company services for our top clients and send it to our CTO
2. Write a linkedin post by myself (works really well if you provide it with materials on how to write good linkedin posts, and who are you and what is important to you when talkint with the world)
3. Reject all of my calendar events for tomorrow (assuming you have a material contaning information on how to access your calendar by an API and what are your credentials)