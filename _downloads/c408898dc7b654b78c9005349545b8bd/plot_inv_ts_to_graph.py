"""
.. _inv_ts_to_graph:

=========================================================
Compute Graph properties from a given connectivity matrix
=========================================================
The inv_ts_to_graph pipeline performs spectral connectivity and graph analysis
over time series .

The **input** data should be a time series matrix in **npy** format.
"""

# Authors: David Meunier <david_meunier_79@hotmail.fr>

# License: BSD (3-clause)

import os.path as op

import nipype.pipeline.engine as pe

from nipype.interfaces.utility import IdentityInterface, Function
import nipype.interfaces.io as nio

#import ephypype
from ephypype.nodes import create_iterator, create_datagrabber
from ephypype.nodes import get_frequency_band
#from ephypype.datasets import fetch_omega_dataset


###############################################################################
# Check if data are available
# needs to import neuropycon_data
# 'pip install neuropycon_data' should do the job...


try:
    import neuropycon_data as nd
except ImportError:
    print("Warning, neuropycon_data not found")
    exit()

data_path = op.join(nd.__path__[0], "data", "data_inv_ts")

###############################################################################
# spectral_connectivity_parameters

freq_bands = [[8, 12], [13, 29]]
freq_band_names = ['alpha', 'beta']


frequency_node = get_frequency_band(freq_band_names, freq_bands)


con_method = 'coh'
epoch_window_length = 3.0

sfreq = 2400
# workflow directory within the `base_dir`
#correl_analysis_name = 'spectral_connectivity_' + con_method

from ephypype.pipelines.ts_to_conmat import create_pipeline_time_series_to_spectral_connectivity # noqa
spectral_workflow = create_pipeline_time_series_to_spectral_connectivity(
    data_path, con_method=con_method,
    epoch_window_length=epoch_window_length)


###############################################################################
# Then, we create our workflow and specify the `base_dir` which tells
# nipype the directory in which to store the outputs.

# workflow directory within the `base_dir`
graph_analysis_name = 'inv_to_graph_analysis'

main_workflow = pe.Workflow(name=graph_analysis_name)
main_workflow.base_dir = data_path

###############################################################################
# Then we create a node to pass input filenames to DataGrabber from nipype

subject_ids = ['sub-0003']  # 'sub-0004', 'sub-0006'
infosource = create_iterator(['subject_id', 'freq_band_name'],
                             [subject_ids, freq_band_names])

#infosource = pe.Node(
        #interface=IdentityInterface(fields=['freq_band_name']),
        #name="infosource")

#infosource.iterables = [('freq_band_name',freq_band_names)]

###############################################################################
# and a node to grab data. The template_args in this node iterate upon
# the values in the infosource node

# template_path = '*%s/conmat_0_coh.npy'
# template_args = [['freq_band_name']
# datasource = create_datagrabber(data_path, template_path, template_args)


template_path = '*%s_task-rest_run-01_meg_0_60_raw_filt_dsamp_ica_ROI_ts.npy'


datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                               outfields=['ts_file']),
                        name='datasource')

datasource.inputs.base_directory = data_path
datasource.inputs.template = template_path

datasource.inputs.template_args = dict(ts_file=[['subject_id']])
datasource.inputs.sort_filelist = True


###############################################################################
# Graphpype creates for us a pipeline which can be connected to these
# nodes (datasource and infosource we created. The connectivity pipeline is implemented by the function
#:func:`graphpype.pipelines.conmat_to_graph.create_pipeline_conmat_to_graph_density`,
# thus to instantiate this graph pipeline node, we import it and pass
# our parameters to it.


# In particular, the follwing parameters are of particular importance:
# density of the threshold

#con_den = 0.1 #
con_den = 0.05 #
#con_den = 0.01 #

# The optimisation sequence
radatools_optim = "WN tfrf 1" 

# see
# http://deim.urv.cat/~sergio.gomez/download.php?f=radatools-5.0-README.txt
# for more details, but very briefly:
# 1) WN for weighted unsigned (typically
# coherence, pli, etc.) and WS for signed (e.g. Pearson correlation) +
# 2) the optimisation sequence, can be used in different order. The sequence
# tfrf is proposed in radatools, and means: t = tabu search , f = fast
# algorithm, r = reposition algorithm and f = fast algorithm (again)
# 3) the last number is the number of repetitions of the algorithm, out of
# which the best one is chosen. The higher the number of repetitions, the
# higher the chance to reach the global maximum, but also the longer the
# computation takes. For testing, 1 is admissible, but it is expected to
# have at least 100 is required for reliable results


# The graph pipeline contains several nodes, some are based on radatools
#
# In particular, the two nodes are:
#
# * :class:`ephypype.interfaces.mne.spectral.SpectralConn` computes spectral connectivity in a given frequency bands
# * :class:`ephypype.interfaces.mne.spectral.PlotSpectralConn` plot connectivity matrix using the |plot_connectivity_circle| function
#
# .. |plot_connectivity_circle| raw:: html
#
#   <a href="http://martinos.org/mne/stable/generated/mne.viz.plot_connectivity_circle.html#mne.viz.plot_connectivity_circle" target="_blank">spectral_connectivity function</a>

from graphpype.pipelines.conmat_to_graph import create_pipeline_conmat_to_graph_density # noqa

graph_workflow = create_pipeline_conmat_to_graph_density(
    data_path, con_den=con_den, optim_seq = radatools_optim)


###############################################################################
# We then connect the nodes two at a time. We connect the output
# of the infosource node to the datasource node.
# So, these two nodes taken together can grab data.

main_workflow.connect(infosource, 'subject_id',
                      datasource, 'subject_id')

main_workflow.connect(infosource, 'freq_band_name',
                      frequency_node, 'freq_band_name')

main_workflow.connect(datasource, 'ts_file',
                      spectral_workflow,"inputnode.ts_file")

spectral_workflow.inputs.inputnode.sfreq = sfreq

main_workflow.connect(frequency_node, 'freq_bands',
                      spectral_workflow, 'inputnode.freq_band')

main_workflow.connect(spectral_workflow, 'spectral.conmat_file',
                      graph_workflow,"inputnode.conmat_file")

###############################################################################
# To do so, we first write the workflow graph (optional)

main_workflow.write_graph(graph2use='colored')  # colored

################################################################################
## and visualize it. Take a moment to pause and notice how the connections
## here correspond to how we connected the nodes.

from scipy.misc import imread  # noqa
import matplotlib.pyplot as plt  # noqa
img = plt.imread(op.join(data_path, graph_analysis_name, 'graph.png'))
plt.figure(figsize=(8, 8))
plt.imshow(img)
plt.axis('off')
plt.show()

################################################################################
## Finally, we are now ready to execute our workflow.

main_workflow.config['execution'] = {'remove_unnecessary_outputs': 'false'}

# Run workflow locally on 2 CPUs
#main_workflow.run(plugin='MultiProc', plugin_args={'n_procs': 2})

# Run workflow
main_workflow.run()








########################################## plotting

from graphpype.utils_visbrain import visu_graph_modules

labels_file = op.join(data_path, "label_names.txt")
coords_file = op.join(data_path, "label_coords.txt")

#for freq_band_name in freq_band_names:

    #res_path = op.join(
        #data_path,graph_analysis_name, "graph_den_pipe_den_0_05",
        #"_freq_band_name_"+freq_band_name)

    #lol_file = op.join(res_path,"community_rada", "Z_List.lol")

    #print(lol_file)

    #net_file = op.join(res_path,"prep_rada", "Z_List.net")

    #visu = visu_graph_modules(lol_file=lol_file, net_file=net_file,
                             #coords_file=coords_file,
                             #labels_file=labels_file,inter_modules=False,
                             #z_offset=+50)
                             ##x_offset=0, y_offset=-20, z_offset=-50)
    ##visu.show()

from visbrain.objects import SceneObj, BrainObj

sc = SceneObj(size=(1000, 1000), bgcolor=(.1, .1, .1))

for nf,freq_band_name in enumerate(freq_band_names):

    res_path = op.join(
        data_path,graph_analysis_name, "graph_den_pipe_den_0_05",
        "_freq_band_name_"+freq_band_name + "_subject_id_sub-0003")

    lol_file = op.join(res_path,"community_rada", "Z_List.lol")

    net_file = op.join(res_path,"prep_rada", "Z_List.net")

    #net_file = op.join(res_path,"net_prop", "Z_List.net")

    b_obj = BrainObj("white", translucent = False)

    sc.add_to_subplot(b_obj, row = nf,use_this_cam=True, rotate='left',
        title=("Module for {} band".format(freq_band_name)),
        title_size=14, title_bold=True, title_color='white')


    c_obj = visu_graph_modules(lol_file=lol_file, net_file=net_file,
                            coords_file=coords_file,
                             labels_file=labels_file,inter_modules=False,
                             z_offset=+50)
                             #x_offset=0, y_offset=-20, z_offset=-50)

    sc.add_to_subplot(c_obj, row=nf)

sc.preview()
