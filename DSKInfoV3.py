#!/usr/bin/env python3
#
# Created by Jason Brooks: www.muckypaws.com and www.muckypawslabs.com
#            7th Febraury 2024
#

import argparse
import os
import sys
import struct

from datetime import datetime

DEFAULT_START_TRACK = 0
DEFAULT_END_TRACK = 42
DEFAULT_HEAD = 0
DEFAULT_DSK_FORMAT = 0

DEFAULT_DSK_TYPE = "DATA"

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
        ('b','numberOfTracks'),
        ('b','numberOfSides'),
        ('h','oldTrackSize'),
        ('<204s','trackSizeTable')
    ]

#
# Define the Sector Information Block Structure
#
class SectorInformationBlock(Structure):
    _fields_ = [
        ('b','Track'),
        ('b','Side'),
        ('b','SectorID'),
        ('b','SectorSize'),
        ('b','FDC1'),
        ('b','FDC2'),
        ('h','notused')
    ]

#
# Define the Track Information Block Structure
#
class TrackInformationBlock(Structure):
    _fields_ = [
        ('<12s','header'),
        ('<4s','unused'),
        ('b','TrackNumber'),
        ('b','TrackSide'),
        ('h','unused2'),
        ('b','sectorSize'),
        ('b','numberOfSectors'),
        ('b','gap3'),
        ('b','filler'),
        #(SectorInformationBlock,'sectorTable[29]')
        ('<232s','sectorTable')
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
    
    sector = table[(SectorPosition*8):(SectorPosition*8)+8]
    track = sector[0]
    side = sector[1]
    sectorID = sector[2]
    sectorSize = sector[3]
    FDC1 = sector[4]
    FDC2 = sector[5]

    FDCStatus = GetFDCStatusText(FDC1, FDC2)

    return track, side, sectorID, sectorSize, FDCStatus 

#
# Get Sector information from Sector Table from TrackID, ie:"07:0" by position (0-numberOfSectors)
#
def GetSectorDataFromSectorTablePosition(TrackID, SectorPosition):
    
    table = DSKDictionary[TrackID].sectorTable

    if SectorPosition > DSKDictionary[TrackID].numberOfSectors:
        return -1, -1, -1, -1, -1, -1, -1
    
    sector = table[(SectorPosition*8):(SectorPosition*8)+8]
    track = sector[0]
    side = sector[1]
    sectorID = sector[2]
    sectorSize = sector[3]
    FDC1 = sector[4]
    FDC2 = sector[5]

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
        if track.TrackNumber >= StartTrack and \
            track.TrackNumber <= EndTrack:

            print(f"\nTrack: {track.TrackNumber:02d}")
            print(" C, H ,  ID,  N, FDC Status")

            for sectors in range(track.numberOfSectors):
                trackNum, side, sectorID, sectorSize, FDCStatus = GetSectorDataFromTrackByPosition(track, sectors )
                print(f"{trackNum:02d}, {side:02d}, #{sectorID:02x}, {sectorSize:02d}, {FDCStatus}")

#
# Print the Disk Header Information
#
def DisplayDiskHeader():
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

            if numberOfSides > 1:
                print(f"Track: {track:02d} Side[{trackside}] - {trackSizeString}")
            else:
                print(f"Track: {track:02d} > {trackSizeString}")


def GetSectorOffset(Track, SectorToFind):
    offset = -1
    for sectors in range(Track.numberOfSectors):
        if Track.sectorTable[(sectors*8)+2] == SectorToFind:
            offset = sectors
    return offset

def normaliseFilename(filename):
    normalName = ""
    for x in range(len(filename)):
        normalName1 = filename[x:x+1] & 0x7f
        
    return normalName
#
# Attempt to show files stored on DISK
#
def DisplayDirectory():
    # Check which File Format
    if DEFAULT_DSK_FORMAT & 1:
        track = 0
        sector = 0xc1
    elif DEFAULT_DSK_FORMAT & 2:
        track = 2
        sector = 0x41
    
    # Always Side 0
    TrackEntry = f"{track:02d}:0"
    
    TrackDict = DSKDictionary[TrackEntry]
    
    SectorSize = TrackDict.sectorSize * 256
    
    offset = GetSectorOffset(TrackDict, sector)
    
    if offset >= 0 and offset < TrackDict.numberOfSectors:
        offset = offset * SectorSize
        
        TrackDataToProcess = DSKDataDictionary[TrackEntry]
        dataToProcess = TrackDataToProcess[offset:offset+SectorSize]
        
        for x in range(8):
            user = dataToProcess[x*32:(x*32)+1]
            if user != 0xe5:
                filename = normaliseFilename( dataToProcess[(x*32)+1:(x*32)+12])
                print(f"{filename}:")
                


#
# Load DSK File to Memory
#
def loadDSKToMemory(filename):
    global DSKDictionary
    global DSKHEAD
    global DSKDataDictionary
    global DSKSectorDictionary
    global DSKSectorDataDictionary
    global DEFAULT_DSK_TYPE
    global DEFAULT_DSK_FORMAT

    if os.path.isfile(filename):
        try:
            with open(filename, mode="rb") as file:
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
                    print("Valid DSK Header Found\n")
                else:
                    print(f"Invalid DSK Header Detected: {validHeader}\n")
                    exit(0)

                #
                # Try processing the DSK information from file.
                DEFAULT_DSK_FORMAT = 0
                if dskHead.numberOfTracks > 0:
                    numberOfSides = DSKDictionary['DiskHeader'].numberOfSides
                    # Parse Number of Tracks 
                    for track in range (DSKDictionary['DiskHeader'].numberOfTracks):
                        # Parse Number of Sides
                        for trackside in range(numberOfSides):
                            tracksize = DSKDictionary['DiskHeader'].trackSizeTable[track] * 256
                            # Check the track is formatted with data.
                            if tracksize > 0:
                                trackString = f"{track:02d}:{trackside:01d}"
                                DSKDictionary[trackString] = TrackInformationBlock(file.read(256))
                                DSKDataDictionary[trackString] = (file.read(tracksize-256))

                                # Check Track-Info is Correctly Set
                                validHeader = DSKDictionary[trackString].header.decode()

                                if validHeader != "Track-Info\r\n":
                                    print(f"Invalid Track Header Detected at Track: {track} - data = {validHeader}\n")
                                    exit(0)


                                # Break out Sector Data
                                sectorCount = DSKDictionary[trackString].numberOfSectors

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
                if DEFAULT_DSK_FORMAT == 1:
                    DEFAULT_DSK_TYPE="DATA"
                elif DEFAULT_DSK_FORMAT == 2:
                    DEFAULT_DSK_TYPE = "SYSTEM"
                elif DEFAULT_DSK_FORMAT == 4:
                    DEFAULT_DSK_TYPE = "IBM"
                else:
                    DEFAULT_DSK_TYPE = "Proprietary"
                                       
                print(f"Disk Format Type: {DEFAULT_DSK_TYPE}\n")

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
    parser.add_argument("-te","--trackEnd", help="End Track to View", type=int, default=99)

    parser.add_argument("-dh","--displayHeader", help="Display Disk Header Information", action="store_true",default=False)
    parser.add_argument("-ds","--displaySector", help="Display Sector Information", action="store_true",default=False)

    parser.add_argument("-dir","--directory", help="Display Directory Information", action="store_true",default=False)

    args = parser.parse_args()

    DEFAULT_START_TRACK = args.trackStart

    # Start up Message
    print("DSK File Info Utility...\n")
    print(f"Processing: {args.filename}\n")
    print(f"Start Track: {DEFAULT_START_TRACK}")

    # Load the File to Memory and Pre-Process it
    loadDSKToMemory(args.filename)

    if args.displayHeader:
        DisplayDiskHeader()

    if args.displaySector:
        DisplaySectorInfo(args.trackStart, args.trackEnd)
        
    if args.directory:
        DisplayDirectory()

