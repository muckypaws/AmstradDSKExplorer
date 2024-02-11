#!/usr/bin/env python3
#
# Created by Jason Brooks: www.muckypaws.com and www.muckypawslabs.com
#            7th Febraury 2024
#
# There's much that can be done to optimise the code
#   Python Coders have to be clinically insane... 
#       I mean seriously... 
#       how difficult does it have to be to perform bitwise operations
#       On Bytes?
#       Apparently F**king difficult...
#       Any normal language... result = byte1 & Byte2
#       PYTHON Devs... 
#           Hold Our Beer... 
#               result = bytes([a & b for a, b in zip(abytes[::-1], bbytes[::-1])][::-1])
#       because... that's logical... init? ffs
#
#   Did I mention how I'm not enjoying Python right now?
#
# V0.02 - 9th February 2024      - A BIT crazy Edition.
#                                  Added code to view directory listing 
#                                  on DSK Files.
# V0.02 - 10th February 2024     - Getting Head Edition.
#                                  Getting File Information 
#                                  Load Address, Length and Execution +
#                                  Filetype
# V0.03 - 10th February 2024     - Bourne Legacy Edition.
#                                  Running tests against 11,000 disks from the community 
#                                  highlighted inconsistencies with file formats
#                                  Circa 1997, in addition to a number of corrupt disks 
#                                  Encoded in the domain.
#                                  Added more processing to detect these anomalies
#                                  Report and handle more gracefully.
# V0.04 - 11th February 2024     - Clive Mobile Edition
#                                  So how much extra effort was required to include
#                                  PLUS3DOS support for the ZX Spectrum Format Disks?
#                                  Not much it seems.
#                                  Produce a list of files, with Load Address, Param 1
#                                  Param2 info.  
#                                  Still experimental...  
'''
    Want to run this tool over multiple files?
    linux use: 
        #!/bin/bash
    find . -name "*.dsk" -type f  -exec python3 DSKInfoV3.py -dir -d  {} \; > FileInfoList.txt
'''
import argparse
import os
import sys
import struct
import datetime 

from datetime import datetime

CONST_AMSTRAD       = 0
CONST_PLUS3DOS    = 1

DEFAULT_START_TRACK = 0
DEFAULT_END_TRACK = 42
DEFAULT_HEAD = 0
DEFAULT_DSK_FORMAT = 0

DEFAULT_DSK_TYPE = "DATA"

DEFAULT_SYSTEM      = CONST_AMSTRAD
GLOBAL_CORRUPTION_FLAG = 0

DSKDictionary = {}
DSKDataDictionary = {}
DSKSectorDictionary = {}
DSKSectorDataDictionary = {}

#
# Helper Class for creating easy structs.
# Nabbed from the O'Reilly Book
#       Python Cookbook 3rd Edition - Recipes for Mastering Python 3
#       ISBN 978-1-449-34037-7
#
class SizedRecord:
    def __init__(self, bytedata):
        self._buffer = memoryview(bytedata)

    @classmethod
    def from_file(cls, f, size_fmt, includes_size=True): 
        sz_nbytes = struct.calcsize(size_fmt)
        sz_bytes = f.read(sz_nbytes)
        sz, = struct.unpack(size_fmt, sz_bytes)
        buf = f.read(sz - includes_size * sz_nbytes) 
        return cls(buf)
    
    def from_buffer(cls, source, offset: int = ...): 
        sz_nbytes = struct.calcsize(source)
        sz, = struct.unpack(source, sz_nbytes)
        buf = sz - includes_size * sz_nbytes
        return cls(buf)
    
    def iter_as(self, code):
        if isinstance(code, str):
            s = struct.Struct(code)
            for off in range(0, len(self._buffer), s.size):
                yield s.unpack_from(self._buffer, off) 
        elif isinstance(code, StructureMeta):
            size = code.struct_size
            for off in range(0, len(self._buffer), size):
                data = self._buffer[off:off+size] 
                yield code(data)

class StructField: 
    '''
        Descriptor representing a simple structure field 
    '''
    def __init__(self, format, offset):
        self.format = format
        self.offset = offset
    
    def __get__(self, instance, cls):
        if instance is None: 
            return self
        else:
            r = struct.unpack_from(self.format,
                                    instance._buffer, self.offset)
            return r[0] if len(r) == 1 else r
    
class NestedStruct: 
    '''
        Descriptor representing a nested structure
    '''
    def __init__(self, name, struct_type, offset):
        self.name = name 
        self.struct_type = struct_type 
        self.offset = offset

    def __get__(self, instance, cls): 
        if instance is None:
            return self 
        else:
            data = instance._buffer[self.offset: self.offset+self.struct_type.struct_size]
            result = self.struct_type(data)
            # Save resulting structure back on instance to avoid 
            # further recomputation of this step setattr(instance, self.name, result)
        return result


class StructureMeta(type): 
    '''
        Metaclass that automatically creates StructField descriptors
    '''
    def __init__(self, clsname, bases, clsdict):
        fields = getattr(self, '_fields_', []) 
        byte_order = ''
        offset = 0
        for format, fieldname in fields:
            if isinstance(format, StructureMeta):
                setattr(self,fieldname,
                        NestedStruct(fieldname, format, offset))
                offset += format.struct_size
            else:
                if format.startswith(('<','>','!','@')): 
                    byte_order = format[0]
                    format = format[1:]
                format = byte_order + format
                setattr(self, fieldname, StructField(format, offset)) 
                offset += struct.calcsize(format)
        setattr(self, 'struct_size', offset)

class Structure(metaclass=StructureMeta):
    def __init__(self, bytedata):
        self._buffer = memoryview(bytedata)

'''
    Back to my code... 
        We're going to define from Python Structs based on the DSK
        File format specified here:
        https://www.cpcwiki.eu/index.php/Format:DSK_disk_image_file_format

        I will also look at the extensions from Simon Owen in a later release.

        https://simonowen.com/misc/extextdsk.txt

        For further extensions to the DSK File Format

'''       
        

#
# Disk Header Structure
#
class DSKHeader(Structure):
    _fields_ = [
        ('<34s','header'), 		
        ('<14s','creator'),
        ('B','numberOfTracks'),
        ('B','numberOfSides'),
        ('h','oldTrackSize'),
        ('<204s','trackSizeTable')
    ]

#
# Define the Sector Information Block Structure
#
class SectorInformationBlock(Structure):
    _fields_ = [
        ('B','Track'),
        ('B','Side'),
        ('B','SectorID'),
        ('B','SectorSize'),
        ('B','FDC1'),
        ('B','FDC2'),
        ('h','notused')
    ]

#
# Define the Track Information Block Structure
#
class TrackInformationBlock(Structure):
    _fields_ = [
        ('<12s','header'),
        ('<4s','unused'),
        ('B','TrackNumber'),
        ('B','TrackSide'),
        ('h','unused2'),
        ('B','sectorSize'),
        ('B','numberOfSectors'),
        ('B','gap3'),
        ('B','filler'),
        #(SectorInformationBlock,'sectorTable[29]')
        ('<232s','sectorTable')
    ]

#
# Define the PLUS3DOS Header
#
class Plus3DOSHeader(Structure):
    _fields_ = [
        ('<8s','header'),
        ('B','SoftEOF'),
        ('B','Issue'),
        ('B','Version'),
        ('<L','TotalFileLen'),
        ('B','FileType'),
        ('<H','Filelen'),
        ('<H','Param1'),
        ('<H','Param2'),
        ('B','Unused'),
        #(SectorInformationBlock,'sectorTable[29]')
        ('<104s','Reserved'),
        ('B','Checksum'),
    ]

#
# Define the PLUS3DOS Header
#
class AmstradFileHeader(Structure):
    _fields_ = [
        ('B', 'User'),
        ('<11s', 'Filename'),
        ('<4s', 'Filler'),
        ('B','BlockNumber'),
        ('B','LastBlock'),
        ('B','FileType'),            
        ('<H','FileSize'),
        ('<H','FileLoad'),
        ('B','FirstBlock'),
        ('<H','LogicalLength'),
        ('<H','EntryAddress'),
        ('<36s','Reserved'),
    ]

#
#   FDC Status Bits are defined in the NEC µPD765A Specification
#   Only Implementing ones identified to date.
#
def GetFDCStatusText(FDC1, FDC2):
    
    if not (FDC1 & FDC2):
        return "Ok"
    
    FDCStatus = ""

    if FDC1&0x80:
        FDCStatus += "End of Cylinder "

    if FDC1&0x20 != 0:
        FDCStatus += "CRC Error "

    if FDC1&0x10:
        FDCStatus += "Overrun "
    
    if FDC1&0x4:
        FDCStatus += "No Data "
    
    if FDC1&0x2:
        FDCStatus += "Write Protect "
    
    if FDC1&0x1:
        FDCStatus += "Missing Address Mark "

    if FDC2&0x40 != 0:
        FDCStatus += "*Control Mark* "

    if FDC2&0x20 != 0:
        FDCStatus += "*Data Error* "

    if FDC2&0x10 != 0:
        FDCStatus += "*Wrong Cylinder* "
    
    if FDC2&0x8 != 0:
        FDCStatus += "*Scan Equal Hit* "

    if FDC2&0x4 != 0:
        FDCStatus += "*Scan Not Satisfied* "

    if FDC2&0x2 != 0:
        FDCStatus += "*Bad Cylinder* "

    if FDC2&0x1 != 0:
        FDCStatus += "*Missing Address Mark* "

    return FDCStatus

#
# Get Sector information from Sector Table by position (0-numberOfSectors)
#
def GetSectorDataFromTrackByPosition(TrackDict, SectorPosition):
    
    table = TrackDict.sectorTable

    if SectorPosition > TrackDict.numberOfSectors:
        return -1, -1, -1, -1, -1, -1, -1
    
    SectorInfo = SectorInformationBlock(table[(SectorPosition*8):(SectorPosition*8)+8])
    track = SectorInfo.Track
    side = SectorInfo.Side
    sectorID = SectorInfo.SectorID
    sectorSize = SectorInfo.SectorSize
    FDC1 = SectorInfo.FDC1
    FDC2 = SectorInfo.FDC2

    FDCStatus = GetFDCStatusText(FDC1, FDC2)

    return track, side, sectorID, sectorSize, FDCStatus 

#
# Get Sector information from Sector Table from TrackID, ie:"07:0" by position (0-numberOfSectors)
#
def GetSectorDataFromSectorTablePosition(TrackID, SectorPosition):

    table = DSKDictionary[TrackID].sectorTable

    if SectorPosition > DSKDictionary[TrackID].numberOfSectors:
        return -1, -1, -1, -1, -1, -1, -1
    
    SectorInfo = SectorInformationBlock(table[(SectorPosition*8):(SectorPosition*8)+8])
    track = SectorInfo.Track
    side = SectorInfo.Side
    sectorID = SectorInfo.SectorID
    sectorSize = SectorInfo.SectorSize
    FDC1 = SectorInfo.FDC1
    FDC2 = SectorInfo.FDC2

    FDCStatus = GetFDCStatusText(FDC1, FDC2)

    return track, side, sectorID, sectorSize, FDCStatus


#
# Display Sector Info for All Sectors
#
def DisplaySectorInfo(StartTrack, EndTrack):
    global DSKDictionary

    print("Sector Information\n")

    trackDict = {k: v for k, v in DSKDictionary.items() if ":" in k}

    for tracks in trackDict:

        track = DSKDictionary[tracks]
        print(f"GAP3: #{track.gap3:02X}, Filler Byte: #{track.filler:02X}")
        if track.TrackNumber >= StartTrack and \
            track.TrackNumber <= EndTrack:

            print(f"\nTrack: {track.TrackNumber:02d}")
            print(" C,  H,  ID,  N, FDC Status")

            for sectors in range(track.numberOfSectors):
                trackNum, side, sectorID, sectorSize, FDCStatus = GetSectorDataFromTrackByPosition(track, sectors )
                print(f"{trackNum:02d}, {side:02d}, #{sectorID:02X}, {sectorSize:02d}, {FDCStatus}")

#
# Print the Disk Header Information
#
def DisplayDiskHeader(verbose):
    global DSKDictionary

    print(f"          Header: {DSKDictionary['DiskHeader'].header.decode()}")
    print(f"    Creator Name: {DSKDictionary['DiskHeader'].creator.decode()}")
    print(f"Number of Tracks: {DSKDictionary['DiskHeader'].numberOfTracks}")
    print(f" Number of Sides: {DSKDictionary['DiskHeader'].numberOfSides}")

    print()

    numberOfSides = DSKDictionary['DiskHeader'].numberOfSides
    # Parse Number of Tracks 
    for track in range (DSKDictionary['DiskHeader'].numberOfTracks):
        # Parse Number of Sides
        for trackside in range(numberOfSides):
            tracksize = DSKDictionary['DiskHeader'].trackSizeTable[track] * 256
            if tracksize > 0:
                trackSizeString = f"Size - {tracksize-256} bytes"
            else:
                trackSizeString = "Unformatted Track"

            trackString = f"{track:02d}:{trackside:01d}"

            if trackString in DSKDictionary:
                sectors = DSKDictionary[trackString].numberOfSectors
                trackSizeString += f", {sectors} Sectors"
            

            if numberOfSides > 1:
                print(f"Track: {track:02d} Side[{trackside}] - {trackSizeString}")
            else:
                print(f"Track: {track:02d} > {trackSizeString}")


def GetSectorOffset(Track, SectorToFind):
    offset = -1

    maxSectors = Track.numberOfSectors
    if maxSectors > 29:
        maxSectors = 29
        print(f"Corrupt number of Sectors Detected in Track: {Track.TrackNumber}, Reporting - {Track.numberOfSectors}")

    for sectors in range(maxSectors):
        if Track.sectorTable[(sectors*8)+2] == SectorToFind:
            offset = sectors
    return offset


#
# Taken from StackOverflow: 
# https://stackoverflow.com/questions/22593822/doing-a-bitwise-operation-on-bytes
#
def andbytes(abytes, bbytes):
    return bytes([a & b for a, b in zip(abytes[::-1], bbytes[::-1])][::-1])

#
# Normalise the Filename
#
def normaliseFilename(filename):
    # Iterate over Filename
    # Bit 7 Indicates Special Features.

    test = bytearray()
    for x in range(len(filename)):
        if filename[x] >= ord(' '):
            test.append(filename[x])
        else:
            test.append(0)


    result=andbytes(test,b'\x7f\x7f\x7f\x7f\x7f\x7f\x7f\x7f\x7f\x7f\x7f')

    normal=result[0:8].decode() + "." + result[8:11].decode()


    return normal

def getFileInfo(track, sector, head):
    global DEFAULT_SYSTEM
    global GLOBAL_CORRUPTION_FLAG

    TrackEntry = f"{track:02d}:{head:01d}"
    
    fileType = b'\x00'
    fileStart = 0
    filelen = 0
    fileexec = 0

    if TrackEntry in DSKDictionary.keys():
        TrackDict = DSKDictionary[TrackEntry]
        
        offset = GetSectorOffset(TrackDict, sector)
        
        if offset >= 0 and offset < TrackDict.numberOfSectors:
            offset = offset * 512
            
            TrackDataToProcess = DSKDataDictionary[TrackEntry]

            if len(TrackDataToProcess) >= (offset+64):
                dataToProcess = TrackDataToProcess[offset:offset+64]
                
                if dataToProcess[:8] != b'PLUS3DOS':
                    FileInfoHeader = AmstradFileHeader(dataToProcess[:64])
                    fileType = int(FileInfoHeader.FileType)
                    fileStart = FileInfoHeader.FileLoad
                    filelen = FileInfoHeader.LogicalLength
                    fileexec = FileInfoHeader.EntryAddress
                    
                else:
                    # Experimental, Process +3DOS Info
                    # Reference : https://area51.dev/sinclair/spectrum/3dos/fileheader/
                    DEFAULT_SYSTEM = CONST_PLUS3DOS
                                        
                    FileInfoHeader = Plus3DOSHeader(dataToProcess)
                    fileType = FileInfoHeader.FileType
                    filelen = FileInfoHeader.Filelen
                    fileStart = FileInfoHeader.Param1
                    fileexec = FileInfoHeader.Param2

            else:
                if GLOBAL_CORRUPTION_FLAG == 0:
                    GLOBAL_CORRUPTION_FLAG = 1
                    print("Warning, Possible Corrupt Disk Detected")
                    print(f"Track Bytes: {len(TrackDataToProcess)} is less than sector pointer - {offset+64}")
    
    return fileType,fileStart, filelen, fileexec

#
# Attempt to show files stored on DISK
# Thankfully Directories are on the Same Track and Incremental Sectors
#
def DisplayDirectory(head, detail):

    if not DEFAULT_DSK_FORMAT:
        print("Error: Default Disk Directory Format Undetected")
        return
    
    # Check which File Format
    if DEFAULT_DSK_FORMAT & 1:
        track = 0
        sector = 0xc1
    elif DEFAULT_DSK_FORMAT & 2:
        track = 2
        sector = 0x41
    elif DEFAULT_DSK_FORMAT & 4:
        track = 1
        sector = 1
    
    FileList = []
    FileListExpanded = []
    
    # The initial sector for start of Track
    initialSector = sector
    # Always Side 0
    for sectorsToSearch in range(4):

        TrackEntry = f"{track:02d}:{head:01d}"
        
        if TrackEntry in DSKDictionary.keys():
            TrackDict = DSKDictionary[TrackEntry]
            
            SectorSize = TrackDict.sectorSize * 256
            
            offset = GetSectorOffset(TrackDict, sector)
            
            if offset >= 0 and offset < TrackDict.numberOfSectors:
                offset = offset * SectorSize
                
                TrackDataToProcess = DSKDataDictionary[TrackEntry]
                dataToProcess = TrackDataToProcess[offset:offset+SectorSize]

                for x in range(16):
                    # Get the CPM User Number 
                    user = dataToProcess[x*32:(x*32)+1]
                    
                    # Technically should validate 0-15 as those were valid, some protection
                    # systems would modify this byte to prevent user intervention
                    if user != b'\xe5' and dataToProcess[(x*32)+1:(x*32)+2] > b' ':
                        offset = (x * 32)+1
                        filename = normaliseFilename( dataToProcess[offset:offset+11] )
                        readonly = dataToProcess[offset+8:offset+9]
                        
                        #Read-Only Flag Set?
                        if readonly[0] > 127:
                            filename += "*"
                        else:
                            filename += " "
                        #System/Hidden Flag Set?
                        hidden = dataToProcess[offset+9:offset+10]
                        if hidden[0] > 127:
                            filename += "+"
                        else:
                            filename += " "

                        # Check First Directory Entry
                        # Extent Byte should be 00
                        #     >0 Related entry to the primary file.
                        extents = dataToProcess[offset+11:offset+12]
                        
                        if extents == b'\x00':
                            # Check Valid Name
                            if filename[0] > " ":
                                entry = f"{user[0]:02d}:"+filename
                                if entry not in FileList:
                                    # Add File to List 
                                    FileList += [entry]
                                    # Get first Cluster ID where File Stored
                                    cluster = int(dataToProcess[offset+15:offset+16][0])
                                    cluster *= 2
                                    ClusterTrack = int((cluster / TrackDict.numberOfSectors ) + track) 
                                    ClusterSector = (cluster % TrackDict.numberOfSectors) + initialSector
                                    filetype, fileStart, fileLen, fileExec = getFileInfo(ClusterTrack, ClusterSector, head)
                                    fileDetails = [f"{user[0]:02d}:" +filename +f"    \t{filetype}\t#{fileStart:04X} \t#{fileLen:04X} \t#{fileExec:04X}"]
                                    #print(fileDetails)
                                    #FileList += [f"{user[0]:02d}:"+filename]
                                    FileListExpanded += fileDetails

        else:
            print(f"Warning, Track Data Not Found For Track: {track}, Head:{head}")
            return 
        # Move to next Sector
        sector = sector + 1

    # De Dupe and Sort
    FileList = sorted(set(FileList))
    FileListExpanded = sorted(set(FileListExpanded))
    

    if len(FileList) == 0:
        print("No files Found, Possible Blank Disk Detected")
    else:
        print(f"Total Files Found: {len(FileList)}\n")
        
        if DEFAULT_SYSTEM == CONST_PLUS3DOS:
            print("*** PLUS3DOS File System Detected ***\n")

        if not detail:
            for filename in FileList:
                print(filename)
        else:
            if DEFAULT_SYSTEM == CONST_AMSTRAD:
                print(" U:Filename    RH  \tType\tStart\tLength\tExec")
                print("-"*53)
            else:
                print(" U:Filename    RH  \tType\tStart\tLength\tParam2")
                print("-"*53)

            for filename in FileListExpanded:
                print(filename)
        
                
#
# Load DSK File to Memory
#
def loadDSKToMemory(filename, verbose):
    global DSKDictionary
    global DSKHEAD
    global DSKDataDictionary
    global DSKSectorDictionary
    global DSKSectorDataDictionary
    global DEFAULT_DSK_TYPE
    global DEFAULT_DSK_FORMAT
    global GLOBAL_CORRUPTION_FLAG

    if os.path.isfile(filename):
        try:
            with open(filename, mode="rb") as file:

                totalFileSize = os.path.getsize(filename)
                # Process the first 256 Bytes - Disk Header Information
                dskHead = DSKHeader(file.read(256))
                DSKDictionary['DiskHeader']=dskHead

                # Check we're dealing with a Valid Disk Format
                # According to the Specification on 
                # https://www.cpcwiki.eu/index.php/Format:DSK_disk_image_file_format
                #
                # There are two VALID Eye Catchers for the Header.
                # "MV - CPCEMU Disk-File\r\nDisk-Info\r\n"
                # "EXTENDED CPC DSK File\r\nDisk-Info\r\n"
                #
                # If either of these don't match then quit.

                validHeader = dskHead.header.decode()

                if validHeader == "EXTENDED CPC DSK File\r\nDisk-Info\r\n" or \
                    validHeader == "MV - CPCEMU Disk-File\r\nDisk-Info\r\n":
                    if verbose:
                        print("Valid DSK Header Found\n")
                elif validHeader[:11] == "MV - CPCEMU":
                    if verbose:
                        print(f"Legacy File Header Discovered: {validHeader}")
                else:
                    print(f"Invalid DSK Header Detected: {validHeader}\n")
                    exit(0)
                
                
                # Check Old Version for Track Info Size
                legacy = 0
                if validHeader != "EXTENDED CPC DSK File\r\nDisk-Info\r\n":
                    legacy = 1

                #
                # Try processing the DSK information from file.
                DEFAULT_DSK_FORMAT = 0
                if dskHead.numberOfTracks > 0:
                    numberOfSides = DSKDictionary['DiskHeader'].numberOfSides
                    # Parse Number of Tracks 
                    for track in range (DSKDictionary['DiskHeader'].numberOfTracks):
                        # Parse Number of Sides
                        for trackside in range(numberOfSides):
                            if not legacy:
                                tracksize = DSKDictionary['DiskHeader'].trackSizeTable[track] * 256
                            else:
                                tracksize = DSKDictionary['DiskHeader'].oldTrackSize
                            # Check the track is formatted with data.

                            # Some Legacy Files Report 40 Tracks when only the relevant ones
                            # Were encoded... So we need to check... 
                            bytesRemaining = file.tell()

                            #if track == 23:
                            #    print("Here")
                            if tracksize > 0 and (bytesRemaining+tracksize)<=totalFileSize:
                                trackString = f"{track:02d}:{trackside:01d}"
                                DSKDictionary[trackString] = TrackInformationBlock(file.read(256))
                                DSKDataDictionary[trackString] = (file.read(tracksize-256))

                                # Check Track-Info is Correctly Set
                                # Some Legacy Disks appear to be corrupt
                                if DSKDictionary[trackString].header[:10] != b'Track-Info':
                                    print(f"Invalid Track Header Detected at Track: {track} - data = {DSKDictionary[trackString].header[:10]}\n")
                                    #exit(0)
                                    return 


                                # Break out Sector Data
                                sectorCount = DSKDictionary[trackString].numberOfSectors

                                # Jacelock would fake/misreport the number of Sectors on a Track
                                if sectorCount > 28:
                                    sectorCount = 28

                                if sectorCount > 0:
                                    x = 0
                                    for sector in range(sectorCount):
                                        sectorData = DSKDictionary[trackString].sectorTable[sector*8:(sector*8)+8]
                                        #print(sectorData , len(sectorData))
                                        if sectorData[2]>=0xc1 and sectorData[2]<=0xc9:
                                            DEFAULT_DSK_FORMAT |= 1
                                        if sectorData[2]>=0x41 and sectorData[2]<=0x49:
                                            DEFAULT_DSK_FORMAT |= 2
                                        if sectorData[2]>=0x1 and sectorData[2]<=0x8:
                                            DEFAULT_DSK_FORMAT |= 4
                                        x += 8
                            else:
                                if GLOBAL_CORRUPTION_FLAG == 0:
                                    GLOBAL_CORRUPTION_FLAG = 1
                                    print(f"Possible Corruption, Insufficient data from Track: {track}")

                # Set Disk Type Flags
                if DEFAULT_DSK_FORMAT == 1:
                    DEFAULT_DSK_TYPE = "DATA"
                elif DEFAULT_DSK_FORMAT == 2:
                    DEFAULT_DSK_TYPE = "SYSTEM"
                elif DEFAULT_DSK_FORMAT == 4:
                    DEFAULT_DSK_TYPE = "IBM"
                else:
                    DEFAULT_DSK_TYPE = "Proprietary"
                                       
                print(f"\nDisk Format Type: {DEFAULT_DSK_TYPE}\n")

        except Exception as error:
            print(f"Failed to open DSK File: {filename}")
            print(f"Error: {error}")
            exit(0)


if __name__ == "__main__":
    # Add user options to the code
    parser = argparse.ArgumentParser(description="Amstrad CPC DSK File Info",
                                     epilog='https://github.com/muckypaws/DSKInfo')

    # Mandatory Parameter - Need a Filename
    parser.add_argument("filename",help="Name of the DSK File to Process")

    # Optional Parameters
    parser.add_argument("-ts","--trackStart", help="Start Track to View", type=int, default=0)
    parser.add_argument("-te","--trackEnd", help="End Track to View", type=int, default=42)

    parser.add_argument("-dh","--displayHeader", help="Display Disk Header Information", action="store_true",default=False)
    parser.add_argument("-ds","--displaySector", help="Display Sector Information", action="store_true",default=False)

    parser.add_argument("-dir","--directory", help="Display Directory Information", action="store_true",default=False)
    parser.add_argument("-s","--side", help="Select Drive Head (0:1)", type=int, default=0)

    parser.add_argument("-v","--verbose", help="Show Startup Parameters", action="store_true",default=False)
    parser.add_argument("-d","--detail", help="Show File Information", action="store_true",default=False)

    args = parser.parse_args()

    

    DEFAULT_START_TRACK = args.trackStart
    DEFAULT_END_TRACK = args.trackEnd

    # Start up Message
    print("\n")
    print("-"*80)
    print("DSK File Info Utility... www.muckypaws.com\n")

    now = datetime.now()
    print(now.strftime("Program Run: %Y-%m-%d %H:%M:%S"))
    print("-"*80)

    print(f"\nProcessing: {args.filename}\n")

    # Check file actually exists before we start...
    if not os.path.isfile(args.filename):
        print(f"\nInvalid Filename, Can't find it: {args.filename}\n")
        exit(0)

    # Check File Size is multiples of 256 bytes
    size = os.path.getsize(args.filename)
    if size % 256:
        print(f"\n\n***Not a valid DSK File: Must be multiples of 256 Bytes: Size = {size}***")

    # Situations for Corrupt DSK files that just contain a header, nothing more
    # I.e. totally unformatted disks
    if size == 256:
        print(f"\n\n*** Sorry, this disk is not formatted ***\n\n")
        exit(0)

    if size <= 1024:
        print(f"\n\n*** Unknown formatted disk, quitting... ***\n\n")
        exit(0)
    
    if args.verbose:
        print(f"Start Track: {DEFAULT_START_TRACK}")
        print(f"  End Track: {DEFAULT_END_TRACK}")
        print(f"       Head: {args.side}")

    # Load the File to Memory and Pre-Process it
    loadDSKToMemory(args.filename, args.verbose)

    if args.displayHeader:
        DisplayDiskHeader(args.verbose)

    if args.displaySector:
        DisplaySectorInfo(args.trackStart, args.trackEnd)
        
    if args.directory:
        DisplayDirectory(args.side, args.detail)

