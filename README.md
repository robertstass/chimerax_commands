# Custom ChimeraX functions
Commands to add extra functionality to ChimeraX.  

Installation instructions can be found at the end of this file.  
Written by Robert Stass, Bowden group, STRUBI/OPIC (2025)

## soft edge mask
Add a soft edge to a mask. This binarizes a mask, extends it and adds a raised cosine soft edge. This is equivalent to relion's relion_mask_create function and CryoSPARC's Volume tools job but works directly in ChimeraX.  
Usage:   
```
soft edge mask #1 level 0.5 extend 2 width 12
```
To binarize at level 0.5, extend the mask by 2 pixels, and add a soft edge with a width of 12 pixels.  
Or

```
soft edge mask #1  
``` 
To use defaults (level=0.5, extend=0, width=12)  
## molmap cube 
Create a volume from an atomic model with a defined box size and pixel size. It's a variant of the molmap command that only creates cube shaped volumes. There are two main benefits. One is to quickly create appropriately sized templates for particle picking or refinement. The second is to help decide an appropriate box size (a box is displayed to easily compare the box size to the target particle).  
Usage:  
```
molmap cube #1 6 200 1.54
```
This creates a 6 Angstrom resolution map with a box size of 200x200x200 pixels at a pixel size of 1.54 Angstrom/pixel. 
## align center 
Aligns the center of atomic models and volumes with each other. The command accepts atomic models or volumes for either input. For volumes the center of mass is calculated. For atomic models, the average position of all the atoms is used to define the center. This is useful to quickly move maps and models around prior to fitting operations.  
Usage:
```
align center #2 to #1
```
or 
```
align center #1 
```
To move model #1 to the center of the current view.  
or
```
align center #2/A to #1 MoveAtomSubset True
```
This will move only chain A of model #2 instead of the whole model.
## rough fitmap
Fit an atomic model in a map without prior manual placement. This first aligns the model to the map with the align center command above. Then uses the fitmap command with global search option. Finally a standard non-search fitmap command can be run to refine the fit. It isn't always successful but I have generally found it to work quite well.  
```
rough fitmap #2 inmap #1
```
Or  
```
rough fitmap #2 inmap #1 search 50 radius 50 refine True
```
To set fitmap search and radius parameters and also repeat the standard fitmap command after rough fit is found. 
Or  
```
rough fitmap #2 inmap #1 sym True refine True
```
For a model with symmetry information in the file header (BIOMT). This doesn't use standard fitmap symmetry option (which is incompatible with global search) but instead pre-symmetrizes the model and fits that. Only works with files that have a BIOMT remark in the header.  
## fit opposite hand
Fit a copy of a model in a map with the handedness reversed. Start with a model that has been fit into a map (that you suspect may have the wrong handedness).
```
fit opposite hand #2 inmap #1 
```
Or 
```
fit opposite hand #2 inmap #1 SkipRoughFit True
```
To avoid first running the "rough fitmap" command above before a standard fitmap command (It often works without it). Other rough fit options can also be supplied.
## map eraser mask create 
Create a spherical mask from the map eraser sphere tool. This is useful to classify potential rare binding partners on the edge of a particle.    
First open a mask with values scaled from 0 to 1. (eg an auto-generated one from a 3D refinement job), and then open the Tools -> Volume data -> Map eraser tool.  
Move the sphere to a desired position. Then run the command to create two masks. One of the sphere only, and another of the sphere combined with the original mask input. A soft edge is automatically added using the soft edge mask command above.
```
map eraser mask create mask #1 sphere #2 width 12
```
or 
```
map eraser mask create mask #1 sphere #2 width 12 save_masks True
```
To automatically save the masks too. (File names can also be specified with file_root, sphere_append and full_append options). 
## Residue shortcuts
A collection of commands including "to residue", "previous residue", "next residue", "first residue" and "last residue" to identify and scroll through residues of a chain. Additionally a button panel is created for quick access to each of these commands. 

Start by making an atomic selection with ctrl+click/drag or with the select command. If multiple residues are selected each command first goes to the first residue of the selection (except "last residue"). Then when a single residue is selected the commands can be used to move to the next residue in the chain or to skip to the beginning or end of the chain. The center of rotation (cofr) is set to the selected residue. A button is provided to reset the cofr for all models in the scene. 

The button panel can be moved into the top bar of ChimeraX. Right click the panel and select "Save tool position" to save the location for future sessions. If you don't want the button panel, comment out the call to create_button_panel() at the end of the chimerax_to_residue.py script. 

## reload scripts 
Reload all the scripts above. This is useful if you edit the scripts themselves and want chimeraX to load the new version without restarting the whole program. It will reload all startup commands (see installation below).
```
reload scripts
```
## Installation
Download the git repository. Open ChimeraX and go to Favourites -> Settings -> Startup.  
Add the following to the "Execute these commands at startup" box:  
```
open <full path to>/chimerax_custom_functions.cxc  
```
where `<full path to>` is the full path to the repository location.  
Then restart chimeraX.