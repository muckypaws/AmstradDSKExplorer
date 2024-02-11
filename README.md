# Amstrad CPC DSK Info Tool

## Created by Jason Brooks - www.muckypaws.com - www.muckypawslabs.com

**Welcome to my little project.**

Recently I've been looking at protection systems of old.  The Community have done an amazing job in digital preservation, looking at ways to archive tapes and disks.

The Amstrad CPC disks are usually identified with the DSK file format, though I have no doubt the ZX Spectrum and others will also use something similar.

The DSK File format is very well documented, and Emulation tools do an amazing job of emulating the subtle nuances these disks posed when certain copy protection techniques were used.

Whilst looking at Emulation vs Real Hardware, I was discovering some anomalies, were these a quirk of emulation or actually physically present on the real thing.

I found myself looking at the internals of these DSK Image files, and needed to speed up looking at bits of information rather than processing through a Hex Editor.

And so this little project is born... 

It's not very exciting at the moment, and I've written it in Python3 to ensure maximum compatibility.  Though I'm still very much a novice at Python Coding... Frankly it seems more complicated than Z80 Assembly...

The code is provided as-is, though if you feel you can contribute to the project, then all is welcome.  Especially anyone who can actually code in Python... 

This is just the beginning but the tool can become much more.

Ideas include...

Ability to extract file from the AMSDOS file format to your device.  IE. Enumerate the file systems files and extract the data direct your filesystem for whatever puposes you decide.

Inject files to the disk.
Convert the DSK from CPM Format to Data, even possibly extract game code from protected disks.

But there are all flights of fancy for another day.

It's very basic right now and probably buggy...

How to use it?

You'll need a Python3 environment either in Windows, macOS, Linux and of course access to DSK Files.

Currently supports the following :-

    Amstrad CPC DSK File format as defined: 
        https://www.cpcwiki.eu/index.php/Format:DSK_disk_image_file_format

    ZX Spectrum +3DOS File Information defined:
        https://area51.dev/sinclair/spectrum/3dos/fileheader/

Commands :-

    -dir            = Directory Listing
    -d              = Combined with -dir for enhanced file information
    -dh             = Show the Disk Header Information
    -ds             = Show Track Sector Information
    -ts             = Starting Track (Default 0)
    -te             = Track End (Default 42)
    -s              = Side (0 = Head 0, 1 = Head 1) Default Head 0
    -v              = Verbose


## python3 DSKUtilV3 -dh filename.dsk

**Displays the Disk Header**

DSK File Info Utility...

    Processing: ./TestDisks/XorOriginal.dsk

    Start Track: 0
    Valid DSK Header Found

            Header: EXTENDED CPC DSK File Disk-Info

        Creator Name: SAMdisk140324
    Number of Tracks: 42
    Number of Sides: 1

    Track: 00 > Size - 4608 bytes, 9 Sectors
    Track: 01 > Size - 4608 bytes, 9 Sectors
    ...
    Track: 39 > Size - 4608 bytes, 9 Sectors
    Track: 40 > Unformatted Track
    Track: 41 > Unformatted Track




## python3 DSKInfoV3.py -ds -ts 17 -te 18 ./TestDisks/XorOriginal.dsk

    **-ds** Display Sector Information
    
    *Optional*
    
    **-ts** Track Start

    **-te** Track End

DSK File Info Utility...

Processing: ./TestDisks/XorOriginal.dsk

    Start Track: 17
    Valid DSK Header Found

    Sector Information


    Track: 17
    C, H ,  ID,  N, FDC Status
    17, 00, #00, 05, Ok

    Track: 18
    C, H ,  ID,  N, FDC Status
    00, 00, #00, 00, Ok
    01, 01, #01, 01, CRC Error *Data Error* 
    02, 02, #02, 02, CRC Error *Data Error* 
    03, 03, #03, 03, CRC Error *Data Error* 
    04, 04, #04, 04, CRC Error *Data Error* 
    05, 05, #05, 05, CRC Error *Data Error* 
    06, 06, #06, 06, CRC Error *Data Error* 
    07, 07, #07, 07, CRC Error *Data Error* 
    08, 08, #08, 08, CRC Error *Data Error* 
    09, 09, #09, 09, CRC Error *Data Error* 
    10, 10, #0a, 10, CRC Error *Data Error* 
    11, 11, #0b, 11, CRC Error *Data Error* 
    12, 12, #0c, 12, CRC Error *Data Error* 
    13, 13, #0d, 13, CRC Error *Data Error* 
    14, 14, #0e, 14, CRC Error *Data Error* 
    15, 15, #0f, 15, CRC Error *Data Error* 

## python3 DSKInfoV3.py -dir ./TestDisks/XorOriginal.dsk

    DSK File Info Utility...

    Processing: ./TestDisks/DizzyHackTutorialFixed.dsk

    Start Track: 0
    End Track: 42
    Valid DSK Header Found

    Disk Format Type: DATA

    Total Files Found: 17

    00:ADAM    .BAS
    00:ADAM    .BIN
    00:CHEAT   .BAS
    00:DIZZYCH .ADM
    00:GETDEC1 .ADM
    00:GETDEC1A.ADM
    00:GETDEC2 .ADM
    00:GETDEC2A.ADM
    00:GETDEC2B.ADM
    00:GETFIRST.ADM
    00:GETREGS .ADM
    00:GETREGS .BIN
    00:LOADER  .ADM
    00:READSECT.ADM
    00:RSX     .ADM
    00:RSX     .BIN
    00:TODISK  .ADM


## python3 DSKInfoV3.py -dir -d ./TestDisks/TheySoldAMillion_SideA.dsk 

Detailed View of the Files in the DSK image, now displaying File Type, Start Address, File Size, Execution Address.

    * means ReadOnly
    + means System/Hidden File

    DSK File Info Utility...

    Processing: ./TestDisks/TheySoldAMillion_SideA.dsk

    Disk Format Type: SYSTEM

    Total Files Found: 8

    U:Filename     RH      Type     Start   Length  Exec
    -----------------------------------------------------
    00:AAAA    .BIN*+       2       #0040   #029F   #0040
    00:BEACH   .SBF*+       2       #8000   #0100   #0000
    00:BPART1  .SBF*+       2       #2100   #7B2A   #0000
    00:BPART2  .SBF*+       2       #2100   #3800   #0000
    00:DALEY   .SBF*+       2       #8000   #003C   #0000
    00:DALEYCDE.SBF*+       2       #0428   #99C0   #0000
    00:MENU    .BIN         2       #3ECE   #011B   #3ECE
    00:TITLEA  .SAD*+       2       #35B5   #22EC   #0000


## ZX Spectrum Plus3DOS

File information is different here,

File Type of 0 = BASIC Program

    Start Address = Line Number to Run
    Start = #8000 = Don't Auto Start
    
    For File Type 0 - BASIC, Param 1 is either the line number 
        to start execution or 0x8000 for none. Param 2 is the 
        offset of variables. For most purposes this can be the 
        length of the program so no variables.

    For File Type 3 - CODE, 
        Param 1 is the load address. 
        Param 2 is unused


    --------------------------------------------------------------------------------
    DSK File Info Utility... www.muckypaws.com

    Program Run: 2024-02-11 17:04:36
    --------------------------------------------------------------------------------

    Processing: ./Midnight Resistance/Midnight Resistance (1990)(Erbe)(+3)(ES)(en)[re-release].dsk

    Possible Corruption, Insufficient data from Track: 32

    Disk Format Type: IBM

    Total Files Found: 10

    *** PLUS3DOS File System Detected ***

    U:Filename    RH  	Type	Start	Length	Param2
    -----------------------------------------------------
    00:BANK0   .         	3	#C000 	#4000 	#8000
    00:BANK1   .         	3	#C000 	#4000 	#8000
    00:BANK3   .         	3	#C000 	#4000 	#8038
    00:BANK4   .         	3	#C000 	#4000 	#8038
    00:BANK6   .         	3	#C000 	#4000 	#8038
    00:BANK7   .         	3	#C000 	#4000 	#8038
    00:DISK    .         	0	#0001 	#003C 	#003C
    00:LOADER  .         	3	#B800 	#06E8 	#8000
    00:MC      .         	3	#7000 	#5000 	#8040
    00:SCREEN  .         	3	#8A00 	#1B00 	#0000