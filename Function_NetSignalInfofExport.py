#!/usr/bin/python3.5
import canmatrix.formats
import logging
import canmatrix.log
import lxml.etree
import canmatrix.formats.arxml
import canmatrix.formats.xlsx

logger = canmatrix.log.setup_logger()
canmatrix.log.set_log_level(logger, -1)


def arxml_file_load(inputfileName):
    #infile = os.getcwd() + "\\"+inputfileName

    cluster = canmatrix.formats.arxml.load(inputfileName)
    if cluster is None:
        logger.debug("cluster loaded is none.")
    tree = lxml.etree.parse(inputfileName)
    ns = "{" + tree.xpath('namespace-uri(.)') + "}"
    return cluster, ns


def dump_signal_info(signalDescriptionDB, inputFileName, outputFolderPath):
    outfile = outputFolderPath+r'\\' + "SignalInfoExport_" + inputFileName + ".xlsx"
    for name in signalDescriptionDB:
        db = signalDescriptionDB[name]
        file_object = open(outfile, "wb")
        #canmatrix.formats.dump(db, file_object,'xlsx')
        canmatrix.formats.xlsx.dump(signalDescriptionDB, file_object)
        file_object.close()


if __name__ == "__main__":
    inputfileName = "xMA_19024_VDDM_190816_AR-4.0.3_Unflattened_Com.arxml"
    cluster, ns = arxml_file_load(inputfileName)
    dump_signal_info(
        cluster, "xMA_19024_VDDM_190816_AR-4.0.3_Unflattened_Com.arxml", ".\\")
