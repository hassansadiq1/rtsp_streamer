import sys

sys.path.append('/opt/nvidia/deepstream/deepstream/lib')
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import GObject, Gst, GstRtspServer
from bus_call import bus_call
from pipeline import Pipeline
import pyds
import json
from datetime import datetime


detector = Pipeline()
dateTimeObj = datetime.now()
file_name = str(dateTimeObj) + '.json'

labels = {0:"person", 1: "bicycle", 2: "car", 3: "motorbike", 4: "aeroplane", 5: "bus",
            6: "train", 7: "truck", 8: "boat", 9: "traffic light", 10: "fire hydrant",
            11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 15: "cat",
            16: "dog", 17: "horse", 18: "sheep", 19: "cow", 20: "elephant", 21: "bear",
            22: "zebra", 23: "giraffe", 24: "backpack", 25: "umbrella", 26: "handbag", 27: "tie",
            28: "suitcase", 29: "frisbee", 30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite",
            34: "baseball bat", 35: "baseball glove", 36: "skateboard", 37: "surfboard", 38: "tennis racket", 39: "bottle",
            40: "wine glass", 41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl", 46: "banana",
            47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog",
            53: "pizza", 54: "donut", 55: "cake", 56: "chair", 57: "sofa", 58: "pottedplant",
            59: "bed", 60: "diningtable", 61: "toilet", 62: "tvmonitor", 63: "laptop", 64: "mouse",
            65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven", 70: "toaster",
            71: "sink", 72: "refrigerator", 73: "book", 74: "clock", 75: "vase", 76: "scissors",
            77: "teddy bear", 78: "hair drier", 79: "toothbrush"}


def osd_sink_pad_buffer_probe(pad,info,u_data):

    global file_name

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.glist_get_nvds_frame_meta()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            #frame_meta = pyds.glist_get_nvds_frame_meta(l_frame.data)
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break

        frame_number=frame_meta.frame_num
        l_obj=frame_meta.obj_meta_list

        while l_obj is not None:
            try:
                # Casting l_obj.data to pyds.NvDsObjectMeta
                #obj_meta=pyds.glist_get_nvds_object_meta(l_obj.data)
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break

            data = {
                "frame_number": frame_number,
                "class" : labels[obj_meta.class_id],
                "left" : int(obj_meta.rect_params.left),
                "top" : int(obj_meta.rect_params.top),
                "width" : int(obj_meta.rect_params.width),
                "height" : int(obj_meta.rect_params.height)
            }
            json_object = json.dumps(data, indent = 4)
            # Writing to sample.json
            with open(file_name, "a") as outfile:
                outfile.write(json_object)
                outfile.write(",\n")

            # print(json_object)
            try: 
                l_obj=l_obj.next
            except StopIteration:
                break

        try:
            l_frame=l_frame.next
        except StopIteration:
            break
			
    return Gst.PadProbeReturn.OK	


def cb_newpad(decodebin, decoder_src_pad, data):
    print("In cb_newpad\n")
    caps = decoder_src_pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()
    source_bin = data
    features = caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    print("gstname=", gstname)
    if gstname.find("video") != -1:
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        print("features=", features)
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad = source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write("Failed to link decoder src pad to source bin ghost pad\n")
        else:
            sys.stderr.write(" Error: Decodebin did not pick nvidia decoder plugin.\n")


def decodebin_child_added(child_proxy, Object, name, user_data):
    print("Decodebin child added:", name, "\n")
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)


def create_source_bin(index, uri):
    print("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name = "source-bin-%02d" % index
    print(bin_name)
    nbin = Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin = Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri", uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added", cb_newpad, nbin)
    uri_decode_bin.connect("child-added", decodebin_child_added, nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin, uri_decode_bin)
    bin_pad = nbin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin


def main(args):
    # Check input arguments
    if len(args) < 4:
        sys.stderr.write("Usage: %s <rtsp input address> <rtsp output port> <mount point>\n" % args[0])
        sys.exit(1)

    # Standard GStreamer initialization
    # GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements */
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    detector.createElements()
    detector.Verify()
    detector.Configure()
    detector.set_tracker_properties()
    detector.ConstructPipeline()

    if not detector._pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    print("Creating Source Bin")
    for i in range(1):
        print("Creating source_bin ", i, " \n ")
        uri_name = args[i + 1]
        if uri_name.find("rtsp://") == 0:
            detector._streammux.set_property('live-source', 1)

        source_bin = create_source_bin(i, uri_name)
        if not source_bin:
            sys.stderr.write("Unable to create source bin \n")
        detector._pipeline.add(source_bin)
        source_bin.link(detector._tee)

        src_pad1 = detector._tee.get_request_pad("src_0")
        if not src_pad1:
            sys.stderr.write("Unable to get tee src pad 1\n")

        src_pad2 = detector._tee.get_request_pad("src_1")
        if not src_pad2:
            sys.stderr.write("Unable to get tee src pad 2\n")

        sink_pad1 = detector._que4.get_static_pad("sink")
        if not sink_pad1:
            sys.stderr.write("Unable to get queue4 sink pad\n")

        padname = "sink_%u" % i
        sink_pad2 = detector._streammux.get_request_pad(padname)
        if not sink_pad2:
            sys.stderr.write("Unable to get streammux sink pad\n")

        src_pad1.link(sink_pad1)
        src_pad2.link(sink_pad2)        

    # create an event loop and feed gstreamer bus mesages to it
    detector._bus = detector._pipeline.get_bus()
    detector._bus.add_signal_watch()
    detector._bus.connect("message", bus_call, detector._loop)

    osdsinkpad = detector._nvosd.get_static_pad("sink")
    if not osdsinkpad:
        sys.stderr.write(" Unable to get sink pad of nvosd \n")

    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    port1 = str(args[i+2])
    port1 = '5' + port1[1:]

    udpsink_port_num_1 = int(port1)

    udp_sink_1 = Gst.ElementFactory.make("udpsink", "udpsink-1")
    if not udp_sink_1:
        sys.stderr.write(" Unable to create udpsink")

    udp_sink_1.set_property('host', '224.224.255.255')
    udp_sink_1.set_property('port', udpsink_port_num_1)
    udp_sink_1.set_property('async', False)
    udp_sink_1.set_property('sync', 0)
    udp_sink_1.set_property("qos", 0)

    detector._pipeline.add(udp_sink_1)
    detector._rtppay1.link(udp_sink_1)

    # Start streaming
    rtsp_port_num_1 = int(args[i + 2])

    server = GstRtspServer.RTSPServer.new()
    server.props.service = f"{rtsp_port_num_1}"
    server.attach(None)

    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch(
        f"( udpsrc name=pay0 port={udpsink_port_num_1} buffer-size=524288 caps=\"application/x-rtp, media=video, clock-rate=90000, encoding-name=(string){detector.ENCODER_CODEC}, payload=96 \" )"
    )
    factory.set_shared(True)
    mount_point = '/' + str(args[i + 3])
    server.get_mount_points().add_factory(mount_point, factory)

    print(f"\n ***Launched Processed RTSP Streaming at rtsp://localhost:{rtsp_port_num_1}{mount_point} ***\n\n")

    port2 = str(args[i+2])
    port2 = '6' + port1[1:]

    udpsink_port_num_2 = int(port2)

    udp_sink_2 = Gst.ElementFactory.make("udpsink", "udpsink-2")
    if not udp_sink_1:
        sys.stderr.write(" Unable to create udpsink")

    udp_sink_2.set_property('host', '224.224.255.255')
    udp_sink_2.set_property('port', udpsink_port_num_2)
    udp_sink_2.set_property('async', False)
    udp_sink_2.set_property('sync', 0)
    udp_sink_2.set_property("qos", 0)

    detector._pipeline.add(udp_sink_2)
    detector._rtppay2.link(udp_sink_2)

    # Start streaming
    rtsp_port_num_2 = rtsp_port_num_1 + 1

    server = GstRtspServer.RTSPServer.new()
    server.props.service = f"{rtsp_port_num_2}"
    server.attach(None)

    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch(
        f"( udpsrc name=pay0 port={udpsink_port_num_2} buffer-size=524288 caps=\"application/x-rtp, media=video, clock-rate=90000, encoding-name=(string){detector.ENCODER_CODEC}, payload=96 \" )"
    )
    factory.set_shared(True)
    mount_point = '/' + str(args[i + 3])
    server.get_mount_points().add_factory(mount_point, factory)

    print(f"\n ***Launched Orignial RTSP Streaming at rtsp://localhost:{rtsp_port_num_2}{mount_point} ***\n\n")

    # List the sources
    print("Now playing...")
    print(args[1])

    print("Starting pipeline \n")
    # start play back and listed to events		
    detector._pipeline.set_state(Gst.State.PLAYING)
    try:
        detector._loop.run()
    except:
        print("error/n/n/n")
    # cleanup
    print("Exiting app\n")
    detector._pipeline.set_state(Gst.State.NULL)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
