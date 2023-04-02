
import os
import base64
from gerber import load_layer
from gerber.render import RenderSettings, theme
from gerber.render.cairo_backend import GerberCairoContext
from PIL import Image
import io
from io import BytesIO
import pandas as pd
import argparse

import glob
import re
import htmlmin



SCALE = 12; 
offset_x = 0; 
offset_y = 0;


def get_snippet (name):

    # Open Snippet File
    file = open(f"snippets.txt", "r");
    d = file.read(); 

    # Create Pattern 
    p = f"@@{name.upper()}_START@@(.*?)@@{name.upper()}_END@@"


    # Search for Snippet Markers
    result = re.search(p,d,re.DOTALL); 
    if result == None:
        print(f"Error: Snippet \"{name.upper()}\" not found, please add to snippet.txt")
        exit()
    snippet = result.group(1).strip()
    file.close()
    return snippet 

def replace_snippet (snippet, name,  text): 
    pattern = f"__{name.upper()}__"
    snippet = snippet.replace(pattern,text)
    return snippet


def get_img (folder, layer, outline):

    global offset_x
    global offset_y


    gerber_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"{folder}/gerber"))
    nc_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"{folder}/nc"))

    #  Load Layers

    # Generate Render 
    gerber = GerberCairoContext(scale=SCALE)
    gerber.units = 'metric'



    if (layer.lower() == "bottom"):
        copper = load_layer(glob.glob (f"{gerber_path}/*.GBL")[0])
        mask = load_layer(glob.glob (f"{gerber_path}/*.GBS")[0])
        silk = load_layer(glob.glob (f"{gerber_path}/*.GBO")[0])
        outline = load_layer(glob.glob (f"{gerber_path}/*.GM{outline}")[0])
        #drillr = load_layer(os.path.join(nc, 'nc-RoundHoles.TXT'))
        #drills = load_layer(os.path.join(nc, 'nc-SlotHoles.TXT'))
        mirror = True
    else: 
        copper = load_layer(glob.glob (f"{gerber_path}/*.GTL")[0])
        mask = load_layer(glob.glob (f"{gerber_path}/*.GTS")[0])
        silk = load_layer(glob.glob (f"{gerber_path}/*.GTO")[0])
        outline = load_layer(glob.glob (f"{gerber_path}/*.GM{outline}")[0])
        #drillr = load_layer(os.path.join(nc, 'nc-RoundHoles.TXT'))
        #drills = load_layer(os.path.join(nc, 'nc-SlotHoles.TXT'))
        mirror = False


    # Generate the offsets and add a margin
    bounds = ((outline.bounds[0][0]-1,  outline.bounds[0][1]+1), (outline.bounds[1][0]-1,  outline.bounds[1][1]+1))
    if mirror == True:
        offset_x = (bounds[0][1])
        offset_y = bounds[1][1] 
    else:
        offset_x = (bounds[0][0] * -1)
        offset_y = bounds[1][1] 

    
    print (bounds)
    print (f"Offset {offset_x}, {offset_y}")

    # Copper    
    render_conf = RenderSettings(color=theme.COLORS['enig copper'], alpha=1.0, mirror=mirror)
    gerber.render_layer(copper, settings=render_conf, bounds=bounds, verbose=True )

    # Mask
    render_conf = RenderSettings(color=theme.COLORS['green soldermask'], alpha=0.8, mirror=mirror, invert=True)
    gerber.render_layer(mask, settings=render_conf, verbose=True)

    # Outline 
    render_conf = RenderSettings(color=theme.COLORS['white'], alpha=1.0, mirror=mirror)
    gerber.render_layer(outline, settings=render_conf, verbose=True)

    # Silk
    render_conf = RenderSettings(color=theme.COLORS['white'], alpha=1.0, mirror=mirror)
    gerber.render_layer(silk, settings=render_conf,verbose=True)

    # Drill
    #render_conf = RenderSettings(color=theme.COLORS['white'], alpha=1.0, mirror=True)
    #gerber.render_layer(drillr, settings=render_conf,verbose=True)

    #render_conf = RenderSettings(color=theme.COLORS['white'], alpha=1.0, mirror=True)
    #gerber.render_layer(drills, settings=render_conf,verbose=True)
    img = Image.open(io.BytesIO(gerber.dump_str()))

    # Make a composite to mask everything
    composite = GerberCairoContext(scale=SCALE)
    composite.units = 'metric'
    bg_conf = RenderSettings(color=theme.COLORS['white'], alpha=1.0, mirror=True)
    render_conf = RenderSettings(color=theme.COLORS['black'], alpha=1.0, mirror=True)
    composite.render_layer(outline, settings=render_conf, bgsettings=bg_conf, bounds=bounds, verbose=True)
    img_composite = Image.open(io.BytesIO(composite.dump_str()))
    return img; 


def translate (x, y, w, h, rotation, mirror=False): 
    if mirror == True:
        x = x * -1
        y = y * -1
    else:
        x = x
        y = y * -1    
    x = (x + offset_x) * SCALE
    y = (y + offset_y) * SCALE
    if (rotation == 0 or rotation == 180 or rotation == 360):
        w, h = h, w
    x = x - ((w/2))
    y = y - ((h/2)) 
    out_x = x  
    out_y = y  
    return {"x": round(out_x),"y": round(out_y),"w": round(w),"h": round(h)}

def get_footprint (footprint):

    if "0402" in footprint:
        l=1.0
        w=0.5
    elif "0603" in footprint:
        l=1.6
        w=0.8
    elif "0805" in footprint:
        l=2.0
        w=1.2
    elif "1210" in footprint:
        l=3.2
        w=2.5
    elif "QFN" in footprint:
        return (80, 80)
    elif "X2SON" in footprint:
        return (20, 20)
    elif "UDFN" in footprint:
        return (12,24)
    else:
        print(f"No Dimensions for {footprint}")
        return (10, 10)


    return (w*SCALE, l*SCALE)    

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Creates an interactive html boardview of your PCB')
    parser.add_argument("pcb", metavar="[PCB]", type=str, help="name of the PCB")
    parser.add_argument("-l", "--layer", default="top", metavar="", type=str, help="specity the layer to show")
    parser.add_argument("-o", "--outline", default="6", metavar="", type=str, help="specity the layer to show")
    args = parser.parse_args()

    if args.layer.lower() == "bottom":
        mirror = True

    img = get_img(args.pcb, args.layer, args.outline)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_data_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    index = 0
    functions = ""
    mirror = False  
    component_table = ""


    # Get BoM and Group with Pandas
    df = pd.read_csv(glob.glob (f"{args.pcb}/pnp/*.csv")[0])
    components = df.groupby(["Footprint",'Value'])


    # Interate through the components
    for key, item in components:
        name = f"show_group_{index}"      # Create Group Name
        desc = f"{key[0]} ({key[1]})"     # Create Description 
  

        # Parse the component group data
        group = components.get_group(key)
        x_list = group["Center-X(mm)"].tolist() 
        y_list = group["Center-Y(mm)"].tolist() 
        r_list = group["Rotation"].tolist() 
        f_list = group["Footprint"].tolist() 
        l_list = group["Layer"].tolist() 

        # skip anything that isnt the layer
        if args.layer.lower() not in l_list[0].lower():
            continue;

        rectangles = ""

        # Get the scaled coordingates 
        for i, x in enumerate(x_list):

            # Get the rectangle cordinates and generate some js. 
            footprint = get_footprint (f_list[i])
            coordinates = translate (float(x_list[i]), float(y_list[i]), footprint[0], footprint[1], float(r_list[i]), mirror)
            tmp = get_snippet ("RECT")
            tmp = replace_snippet (tmp,"X", f"{coordinates['x']}")
            tmp = replace_snippet (tmp,"Y", f"{coordinates['y']}")
            tmp = replace_snippet (tmp,"W", f"{coordinates['w']}")
            tmp = replace_snippet (tmp,"H", f"{coordinates['h']}")
            rectangles+=tmp

        # Create component table entry
        tmp = get_snippet ("TABLE")
        tmp = replace_snippet (tmp,"NAME", name)
        tmp = replace_snippet (tmp,"QTY", f"{len(x_list)}")
        tmp = replace_snippet (tmp,"PART", f"{key[1]}")
        tmp = replace_snippet (tmp,"PART_LINK", f"http://www.google.com/search?q={key[1]}")
        tmp = replace_snippet (tmp,"FOOTPRINT", f"{key[0]}")

        component_table += tmp; 

        # Create onClick javascript calls
        tmp = get_snippet ("ONCLICK")
        tmp = replace_snippet (tmp,"NAME", name)
        tmp = replace_snippet (tmp,"RECTS", rectangles)
        tmp+="\n\n"
        functions+=tmp
        index+=1

    html = get_snippet ("HTML")
    html = replace_snippet(html, "IMAGE_DATA",img_data_b64)
    html = replace_snippet(html, "CANVAS_WIDTH",f"{img.size[0]}")
    html = replace_snippet(html, "CANVAS_HEIGHT",f"{img.size[1]}")
    html = replace_snippet(html, "COMPONENT_TABLE",component_table)
    html = replace_snippet(html, "ONCLICK_FUNCTIONS",functions)

    
    minified = htmlmin.minify(html, remove_empty_space=True)
    # Parse HTML
    f = open(f"{args.pcb}/{args.pcb}-boardview.html", "w")
    f.write (minified)
    f.close()


