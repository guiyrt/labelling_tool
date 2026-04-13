# CAUTION
The output file is named exactly as the datatable you load into the tool! Make sure that your datatables have a unique name, otherwise the earlier files are overwritten and the data is lost!

Example: If all your data table files are named "track_label_position.parquet", rename them to "track_label_position1.parquet", "track_label_position2.parquet", "track_label_position3.parquet" and so on.


# Overview
This repository contains a tool which: 
- loads and playes a screen recording in the .mkv format
- loads a datatable in the .parquet file format
- lets the user create a list of predefined tasks
- saves the tasks in a json-formatted file

# Output Format
The output files are stored in ~/code/output. Each assigned task has the following properties: 
- key: "id" - an id (unique per file, not unique among multiple files)
- key: "start" - the start time of a task in the format "yyyy-mm-dd hh:mm:ss.3f"
- key: "end" - the end time of a task in the format "yyyy-mm-dd hh:mm:ss.3f"
- key: "callsigns" - a list of the callsigns of all aircraft involved in the task
- key: "task_type" - an integer describing the task

## Task Types: 
1  -->  Aircraft Request

2  -->  Assume

3  -->  Conflict Resolution

4  -->  Entry Conditions

5  -->  Entry Conflict Resolution

6  -->  Entry Coordination

7  -->  Exit Conditions

8  -->  Exit Conflict Resolution

9  -->  Exit Coordination

10 -->  Non Conformance Resolution

11 -->  Quality of Service

12 -->  Return to Route

13 -->  Transfer

14 -->  Zone Conflict

# Package Dependencies
Your virtual environment requires the following packages: 
numpy (v1.26.4), pandas (v3.0.1), PyQt6 (v6.10.2), PyQt6-Qt6 (v6.10.2), PyQt6_sip (v13.11.1), json, datetime, sys, subprocess


# How to Use
Copy the repository and open the directory in your IDE of choice (which is, if you got your head together, visual studio code). Open the file "main.py" and click run. The program should now open a user interface as depicted below. 

<img width="1232" height="1118" alt="UI_Overview" src="https://github.zhaw.ch/user-attachments/assets/684753bf-8a76-463b-9988-7405bb625fbb" />

## Importing the Files
First, the video and the datatable must be imported. Click on the "Load Video" button in the import section and select the screen recording you want to use. The file must be in the "\*.mkv" format. Second, click on the "Load Data" button and select a datatable. The table must be in the "\*.parquet" format. 

## Video Player
The video player has pretty standardized controls. A video slider indicates the current position of the video. The time can be changed by drag-and-drop on the slider. From the left to the right, the control buttons are "Play", "Pause" and "Stop". The buttons "-10s" up to "+10s" change the current time by the corresponding time increment. The video can also be used with keyboard shortcuts: 

SPACE: Toggle Play/Pause
Left/Right Arrow: -1s / +1s
a: -10s
s: -1s
d: +1s
f: +10s

## Create Tasks
To create a task, the user can select any task type from the dropdown menu. By clicking on the buttons "Set Start/Stop Time", the program sets the current time of the video as start/stop time. You can press multiple times on the same button to re-define the start time. In the drop down menu to the right, a list of aircraft is available. You can select any aircraft by its callsign and assign it to the task by clicking the "Add to Task" button. If you want to remove the aircraft from a task (e.g. if you misclicked), click on the "Remove All" button. To save the task, click on the green button saying "Save task". 

The yellow "Clear button" clears all information of the task which is currently to be created. The red "delete button" deletes a task which already exists. 

### List of Aircraft
The dropdown menu depicting the list of aircraft lists all aircraft callsigns in a 5min sliding window (hence t-2.5min up to t+2.5min). If you want to adapt this sliding window, you can change the time window in the code. Open the file "MainUI.py" and define the variable "window" in the function "_on_video_position_changed" to the desired time window. 

## Edit Tasks
Any task which is created can be edited. You can select a task in the dropdown menu with the label "Loaded Task". Selecting a task there lets you define all properties completely new. Just re-save the task as described above. You can also select a task by clicking on the orange marker on the video slider. 

<img width="786" height="233" alt="Bildschirmfoto 2026-04-08 um 10 18 38" src="https://github.zhaw.ch/user-attachments/assets/511c45ba-bd9c-4eaf-8a25-b28de7bf85f5" />

## Output
The output file is stored in the directory "~/code/output". 

CAUTION: The output file is named exactly as the datatable you load into the tool! Make sure that your datatables have a unique name, otherwise the earlier files are overwritten and the data is lost! 


