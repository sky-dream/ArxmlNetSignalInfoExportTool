# ArxmlNetSignalInfofExportTool
A simple Pyqt5 GUI tool used to export net signals info into Excel table.

This tool is based on the python library [ebroecker/canmatrix](https://github.com/ebroecker/canmatrix) from Eduard Broecker.

output table format as below,

|ID|Frame Name|Cycle Time [ms]|Launch Type|Launch Parameter|PDU_Name|PDU_Type|PDU_Length|PDU_PortType|Signal Byte No.|Signal Bit No.	| Signal Name	|Signal Function|Signal Length [Bit]	|Signal Default	|Signal Not Available	|Byteorder|Value|Name / Phys. Range|Function / Increment Unit|Signal_Group| 
| ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| 49-1-32h	| FrTrFlexrayFr04 | 160	| cyclicX	| 	| XXXXXXSignalIPdu04	| I-SIGNAL-I-PDU	| 32	| IPduPort_Out	| 1	| 3	| XXXSafeCntr		|counter	| 4	| 0		| 	| m			| | -8..7		|	| XXXSetSafe| 
