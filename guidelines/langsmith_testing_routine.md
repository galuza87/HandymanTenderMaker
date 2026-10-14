---

tags:

- llm
- langsmith
- python
- routine
- testing created: 2026-10-10

---

# Prerequisites

- Installations of python packages: langsmith, langchain, langchain-openai, Langgraph-CLI
- Env. variables are defined: LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
- Routes to the agent nodes are defined in: langgraph.json

# Basic entities

### 1 Traces

> [!note] Hands-on Example "Traces" [LangChain Youtube video](https://www.youtube.com/watch?v=fA9b4D8IsPQ&list=PLfaIDFEXuae2CjNiTeqXG5r8n9rld9qQu) **Traces** are the interactive log of the Agent calls in the application.

> Open the tab on left "Tracing" it will show the tracing projects for the account and their basic statistic as well as billing costs.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260903194653.png">
> 
> A tracing project is a collection of traces or logs associated with my application.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260903194933.png">
> 
> Clicking on the trace will provide more information.  
> It describes everyhing that has happened in our system as well as the final output.  
> Call chain, nodes, call to LLM, tool usage.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260903195138.png">
> 
> Click on a particular step to view more information about it.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260903200020.png">
> 
> Hover over a particular step at the left hand side to see helpful telemetry about it.  
> Including the tokens and latency cost.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260903200543.png">
> 
> Click on the Waterfall button to view different sources of latency.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260903202701.png">

### 2 Types Of Runs

> [!note] Hands-on Example "Types of runs" [LangChain Youtube video](https://www.youtube.com/watch?v=WplpUxEyl9o&list=PLfaIDFEXuae2CjNiTeqXG5r8n9rld9qQu&index=2) Type of **run** is a type of component being traced.

> You can configure it in the `@Traceable` decorator.  
> For LangChain native code the type is indicated automatically.  
> For example `@Traceable{run_type='llm'}`
> 
> - <img src="./_assets/LangSmith/Pasted%20image%2020260904235956.png"> LLM - a call to an LLM
> - <img src="./_assets/LangSmith/Pasted%20image%2020260905000011.png"> Retriever - retrieves documents from DBs or other sources
> - <img src="./_assets/LangSmith/Pasted%20image%2020260905000022.png"> Tool - executes actions with function tools
> - <img src="./_assets/LangSmith/Pasted%20image%2020260905000035.png"> Chain - the default run type, combines multiple Runs together
> - <img src="./_assets/LangSmith/Pasted%20image%2020260905000048.png"> Prompt - hydrates a prompt to be used with an LLM
> - <img src="./_assets/LangSmith/Pasted%20image%2020260905000105.png"> Parser - extracts structured data
> 
> Let's compare a call to an LLM with and without the run_type.  
> Open the list of Runs instead of Traces, by clicking on Runs:  
> <img src="./_assets/LangSmith/Pasted%20image%2020260905001120.png">  
Then choose both calls, and click "Compare Runs".   
**Note: I don't find the ability to compare.**  
> We will see the runs compared side by side.  
> The decorated call has a specific icon and is also possible to filter.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260905001635.png">
> 
> **LLM Run** has a special ability to run in a Playground.  
<img src="./_assets/LangSmith/Pasted%20image%2020260905002723.png">  
> It brings this exact LLM call into the playground interface.  
> It allows to quickly change the promt and see how it affects the output.
> 
> **Retriver Run** shows nicely the list of retrieved documents in the output.
> 
> **Tool Run** shows the input and output of the function that is used in the next step of the call chain

# Single run tests

### 3 Debugging with Langsmith Studio IDE

> [!note] Hands-on Example "Debugging with Studio" [LangChain Youtube video](https://youtu.be/NJXu-4nDo50?si=RI2qL46Gn0RXMcl7) **Studio** is the native LangSmith IDE, opened inside of the browser window.

> `langgraph.json` tells Langsmith where our agents are in the codebase.  
This example has 3 agents located in `graphs.py`: <img src="./_assets/LangSmith/Pasted%20image%2020260913184045.png">
> 
> DeepAgents also should be specified in the file. <img src="./_assets/LangSmith/Pasted%20image%2020260913191200.png">  
The compiled graphs are our agents that we specify in the congifg file above. <img src="./_assets/LangSmith/Pasted%20image%2020260913184336.png">  
Once we have implemented our agents, we can run Studio from the Terminal.
> 
> As prerequisite you should have Langgraph-CLI package instaleld in the environment.
> 
> ```bash
> pip install -U "langgraph-cli[inmem]" 
> ```
> 
> [LangGraph CLI Homepage](https://docs.langchain.com/langsmith/cli)
> 
> Type `langgraph dev` in the Terminal.
> 
> <img src="./_assets/LangSmith/Pasted%20image%2020260913190429.png">
> 
> Studio opens in the browser. Now we can run our agents and debug them. <img src="./_assets/LangSmith/Pasted%20image%2020260913212237.png">
> 
> If blockbuster complains about synchronous blocking calls, you can ignore the warnings by statrting: `langgraph dev --allow-blocking`
> 
> Select the agent at the top drop-down menu:  
<img src="./_assets/LangSmith/Pasted%20image%2020260913212515.png">  
We can interact with our agent by sending a message to it in the bottom window.  
Fill the required fields and see how the graph executes different nodes and changes the state at each step.  
We can switch to "Trace" view to see the trace that was generated by our execution.  
<img src="./_assets/LangSmith/Pasted%20image%2020260913213613.png">
> 
> You can also make changes to the application and the Studio will hot-reload the agent, so you can quick test the changes.  
> **Refresh the Studio page for hot-reload.**
> 
> **Interrupts** let us set breakpoints in our agetn's execution.  
<img src="./_assets/LangSmith/Pasted%20image%2020260913215309.png">  
If we send a message again, we see that our agent pauses at the breakpoints.  
Inspect the state and click "continue".
> 
> **Forking** lets us go back to previous execution steps and alternate the state of the agent, to see how it influences.  
Hower a step name in the Interact view and press the pencil icon that appears to edit the state and press the Fork button.  
Observe the new execution with same breakpoints.  
<img src="./_assets/LangSmith/Pasted%20image%2020260913220139.png">

### 4 Playground and Prompts

> [!note] Hands-on Example "Playground and Prompts" [LangChain Youtube video](https://www.youtube.com/watch?v=h4f6bIWGkog) **Prompts** are our saved prompts that we want to reuse. **Playground** is a sandbox to test and play with our prompts.

> Playground and Prompts are available on the left menu of LangSmith website.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260916225608.png">  
You also can access the Playground through a trace containing an LLM call, at top right corner:  
<img src="./_assets/LangSmith/Pasted%20image%2020260916231609.png">  
We can modify the input here to see how it changes the output.  
> Press the Start button at the top right.  
<img src="./_assets/LangSmith/Pasted%20image%2020260916231928.png">  
You can also choose another LLM model by clicking on the button with the name of the model:  
<img src="./_assets/LangSmith/Pasted%20image%2020260916232825.png">.  
> Once you are satisfied with the prompt, you can save it.
> 
> We don't want to save a specific question and the content hardcoded into the prompt.  
> Replace them with input variables {question} and {context}.  
> By using Input variables we can use the specific question and context from the dialog rather than pulling it from our trace.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918115914.png">  
Click the Save button and give the prompt a name.
> 
> We can now view the prompt in the Prompts tab.  
> It is possible to continue making changes to the prompt and run it in Playground again. That will generate more "Commits".  
> To use our prompt in the application, we are provided with a snippet of code at the bottom of the page.  
This allows us avoid hard-coding the prompt into our application. We can pull different versions of our prompt.  
We can optimize our prompt in Playground clicking on:  
<img src="./_assets/LangSmith/Pasted%20image%2020260918120822.png">  
It uses an LLM agent through the LangSmith chat that helps optimize my prompt.  
> _The "Prompts Canvas" has been discarded._  
> <img src="./_assets/LangSmith/Pasted%20image%2020260918140551.png">  
Insert your instruction to improve the prompt and observe the result.  
> Click "Use this version" and commit the changes.  
> To use a particular commit of our prompt in our application, add the particular commit hash that you would like to use:  
> <img src="./_assets/LangSmith/Pasted%20image%2020260918140741.png">

# Mass tests

### 5 Offline evaluations

> [!note] Hands-on Example "Datasets and Evaluations" [LangChain Youtube video](https://www.youtube.com/watch?v=iEgjJyk3aTw) **Offline Evaluations** are evaluation functions that we can call without executing our application call.

> Offline evaluations are achieved using Datasets and Experiments. We can upload or create a dataset with frequent questions and answers.  
> By navigating to the Datasets section we can either upload a csv or json file or create our own from scratch.  
> Press the button at top left:  
<img src="./_assets/LangSmith/Pasted%20image%2020260918174724.png">  
> Defining the Input and Output Schema lets us decide which fields we expect in our dataset.  
Default:  
<img src="./_assets/LangSmith/Pasted%20image%2020260918174917.png">  
Let's try the Open-AI standard:  
> <img src="./_assets/LangSmith/Pasted%20image%2020260918175020.png">  
<img src="./_assets/LangSmith/Pasted%20image%2020260918175109.png">
> 
> We can add an example by clicking "Add Example" button and typing it in manually.  
Alternitevely we can add AI-generated examples using the same button.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260918175757.png">
> 
> This will use the existing examples in the dataset to create new ones.  
> You must define the Input and Output schema first to use this option.  
You also need a developer subsription to platform.openai.com and use the OPEN_API_KEY only.  
> No option to use local LLM through LM Studio here.
> 
> Open-AI format Input.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260918175253.png">
> 
> Click on "+Message" to add human message.  
> <img src="./_assets/LangSmith/Pasted%20image%2020260918175515.png">
> 
> And the output:  
<img src="./_assets/LangSmith/Pasted%20image%2020260918175556.png">
> 
> We can also add example from our project Traces. When selecting the traces in check box a button appears. We can add many traces at bulk.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918185133.png">
> 
> **Experiments** We can run Experiments against the Golden Dataset. Press "New Experiment". We get python snippets to run in our local environment.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918231600.png">  
We need to define our evaluators, functions that evaluate some metric. It can be a **"Custom Code Evaluator"** for close-ended metrics.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918231737.png">  
Or **"LLM-as-a-Judge Evaluator"** for open-ended metrics.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918232018.png">
> 
> This correctness evaluator defines a rubric that the LLM will use while scoring. <img src="./_assets/LangSmith/Pasted%20image%2020260918232228.png">  
And for each example it gives LLM access to the input and the reference output in addition to output of the application.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918232322.png">  
So it will compare the LLM output to the reference output.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918232516.png">  
Finaly we define a function that runs our application on the dataset.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918232615.png">  
Now we are ready to run the experiment.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918232651.png">  
To observe the result of the experiment got to the Experiments tab, click on the golden dataset that we used.  
And see the list of experiments with columns for each of our evaluators.
> 
> **"Automatic Evaluator"** runs on every experiment in background.  
To create one, click on the "Evaluators" button on the top right.  
It lets us "create from scratch" or use templates. Defining LLM-as-a-judge we define the prompt and the model to use.  
We build the prompt the same way witj Rubric, Instructions, Input, Output and reference Output.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918233504.png">
> 
> Clicking on each experiment will show us a table showing how our model score on each example.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918233551.png">
> 
> If we select two experiments in check box, we can compare how two models performed differentely. We can choose the metric to compare.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918233728.png">

### 6 Annotation Queues

> [!note] Hands-on Example "Annotation Queues" [LangChain Youtube video](https://www.youtube.com/watch?v=rxKYHA-2KS0) **Annotation Queue** is a way to leave feedback on performance of the application. It allows to leverage human feedback to improve the application over time.

> Create new annotation queue in "Annotation Queues" tab. Default Dataset of the Annotation Queue is the set where the annotations are saved when we are done with them. For example our Golden Dataset. We can give the reviewers some instructions. We can specify what feedback to give. We can take different predefined parameters from the list and define categories.  
<img src="./_assets/LangSmith/Pasted%20image%2020260921112157.png">
> 
> To add a trace to the Anntoation Queue, select it's checkbox and press the button: <img src="./_assets/LangSmith/Pasted%20image%2020260918235654.png">
> 
> When opened the entry from queue we see the inout and the output as well as the space for the review text and ability to identify the score.  
<img src="./_assets/LangSmith/Pasted%20image%2020260918235933.png">  
Move to the next annotation, by clicking "Done", or move the reviewed annotation to the default dataset. I also can alternate the output as the reviewer I can modify the output so it will be correct, change the feedback to "correct" and save it to the golden dataset.

> The ID of the queue is visible in the adress bar:  
<img src="./_assets/LangSmith/Pasted%20image%2020260921195221.png">

### 7 Automations and Online Evaluation

> [!note] Hands-on Example "Automations and Online Evaluation" [LangChain Youtube video](https://www.youtube.com/watch?v=z69cBXTJFZ0) **Automation** is a rule to run on every trace sent to our production application. **Online evaluations** are a type of automation that help you measure metrics on your application's output. And run on live production user interactions, not on a curated data set.

> In Tracing Project tab, to create a new automation, you can use the **Rules** button in the top right. Use a filter to define which runs the rule will execute on.

> Sampling rate lets run the rule on a subset of the traces that meet a filter criteria. Useful for expensive automations, like LLM-as-a-judge. You also have the ability to apply your rule to past runs.

> There is a list of actions you can actually execute with your automation. You can add the selected traces to an annotation queue or to a dataset. You can also apply an evaluator to the selected traces and add feedback to them.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919105753.png">

> Just like in offline evaluations, you can create an LLM-as-a-judge or a custom code evaluator to run on your traces. The only difference is that **you won't have reference outputs** to use in your evaluation because you'll be running over production traces rather than a curated dataset.

> Next, you can also trigger webhooks from automations. This can be useful for workflows like creating a Jira ticket when trace errors occur. For alerting flows, you have the option of configuring an alert directly using PagerDuty.

> Finally, you can use automations to extend the retention period for your traces, as the default trace lifespan is 14 days unless you've added feedback to it or added it to a dataset.

> _**Evaluate the quality**_ An example of online evaluator using an updated version of our Simplicity evaluator from previous videos. The prompt is the same.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919110054.png">
> 
> We still provide the LLM the input and the output of our trace, but we don't have a reference output to provide anymore.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919110156.png">
> 
> If we scroll further down, you can see that we've also updated the scoring to be from 1 to 10.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919110233.png">

> _**Mark potential Golden Dataset candidates**_ Next example is the Simplicity Sample Review, and it takes a subset of traces with **high simplicity scores** and adds them to an annotation queue.

> Rules that add feedback to a trace will send the trace **back** through our **other automations** to ensure that any rules triggered **off of feedback** are properly fired.

> See the feedback of rules in the logs of the rule.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919111144.png">

> The feedback is also visible in the tracing project tab. It will show up in the feedback column at the right.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919111333.png">

### 8 Dashboards

> [!note] Hands-on Example "Dashboards" [LangChain Youtube video](https://www.youtube.com/watch?v=VxsIvf9NdxI) **Dashboards** is the way that LangSmith provides monitoring tools for analyzing application performance in production, including trace volume, latency, errors, token usage, cost, and evaluator feedback.

> 1. Open **Monitoring Dashboard** from the left-hand navigation. LangSmith provides pre-built dashboards, including dashboards configured for individual projects.

> A dashboard can include:
> 
> - Trace count over time — indicates application usage.
> - Latency — helps identify performance issues.
> - Error rate — helps identify incidents and regressions.
> - LLM call statistics.
> - Cost charts.
> - Input and output token usage.
> - Tool performance, including latency and errors.
> - Run-type breakdowns.
> - Evaluator feedback that we have configured.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919145603.png">

> For an application with one LLM call per run, LLM call count corresponds directly to trace count.

> 2. Create a Custom Dashboard Open **Monitoring → Custom Dashboards** and create a new dashboard. Specify a name and description. Then create a new chart and configure its name and description. Select projects for the chart. A chart can use data from one or multiple projects. This allows metrics to be compared across applications or monitored at the organization level.

> We can Filter Traces that will get to the chart. For example: - Feedback: `simplicity`, Score: `> 7`

> Choose the metric to display. **Run count** shows how many traces match the filter. **Average latency** shows the average execution time of the matching traces. Other feedback metrics can also be charted. For example, select:
> 
> - Metric: **Average feedback score** -> Feedback: **Correctness**
> - Chart type: **Bar chart**

> <img src="./_assets/LangSmith/Pasted%20image%2020260919150336.png">

> Use the **Group** feature to split data into multiple series. Data can be grouped by attributes such as:
> 
> - Run type
> - Attached metadata  
<img src="./_assets/LangSmith/Pasted%20image%2020260919150411.png">

> For example, select **Run type**, clear the existing filters, and use **Latency** as the metric to compare latency across different run types.  
<img src="./_assets/LangSmith/Pasted%20image%2020260919150515.png">

> Saved charts can be accessed later from the **Custom Dashboard**.