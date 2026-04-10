///////////////////////////////////////////////////////////////////////////

    - Star CUPS Driver Ver. 3.17.0 for linux -
        Readme File                                    19/05/2025

   (C) 2004 - 2025 Star Micronics Co., Ltd. All rights reserved.
///////////////////////////////////////////////////////////////////////////

*This ReadMe File applies to Star CUPS Driver Ver. 3.17.0 for Linux
*This file provides supplementary information that is not described in other
 documentation.

  Thank you very much for purchasing Star Printer.

  Contents:

  1. About "Star CUPS Driver Ver. 3.17.0"
  2. Cautions When printing via a USB interface
  3. How to send RAW Data to CUPS Printer
  4. TSP100IIU Vertical Compression Print and Back Feed Function Setting
  5. Release History

======================================
 1.About "Star CUPS Driver Ver.3.17.0"
======================================
- Added MCL21
- Supported halftoning option with MCL21, MCL32
- Supported ChromeOS (Linux development environment only)

===================
 2.Supported Models
===================
This Software supports the following Star Micronics Printer models:

- mC-Print2
- mC-Print3
- mPOP
- BSC10II
- TSP100IV
- TSP100IV SK
- TSP100IIILAN
- TSP100IIIW
- TSP100IIIBI
- TSP100IIIU
- TSP100IIU
- TSP650II
- TSP700II
- TSP800II
- mC-Label2
- mC-Label3
- SP700
- SK1-211/221
- SK1-311/321
- SK1-41
- SK5-31

=============================================
 3.Cautions When printing via a USB interface
=============================================
When printing via a USB interface, the printing speed
dramatically may decrease or printing jobs may fail.

If this happens, use the script ("setup_for_linux.sh") in the
"SourceCode"-->"Tips"-->"MSW_Setting" folder in the "Star_CUPS_Driver-X.X.X_linux.zip" (X.X.X
represents the driver version) in this driver package.
This will improve the problems described above.

Read the comments in the script for details on how it is used.

=======================================
 4.How to send RAW Data to CUPS Printer
=======================================
If you want to send RAW data file to Printer without any filtering,
you can use "-oraw" option of the "LPR" command.

Please refer to the following places for details.

"SourceCode"-->"Tips"-->"HowToSendRawDataViaCUPS20060725.tar" folder
in the "Star_CUPS_Driver-X.X.X_linux.zip" (X.X.X represents the driver version)
in this driver package.

======================================================================
 5.TSP100IIU Vertical Compression Print and Back Feed Function Setting
======================================================================
* This setting applies to Star TSP100IIU.
Please refer to the following places for the Vertical Compression Print and Back Feed Function Setting.

Please execute the script("BackFeed_default.sh")in the "SourceCode"-->"Tips"-->"TSP100IIU" folder in the
"Star_CUPS_Driver-X.X.X_linux.zip" (X.X.X represents the driver version)in this driver package.

The reduction print setting is 13 of the following.
  1.Back Feed default setting
  2.Back Feed 11mm setting
  3.Back Feed 10mm setting
  4.Back Feed  9mm setting
  5.Back Feed  8mm setting
  6.Back Feed  7mm setting
  7.Back Feed  6mm setting
  8.Back Feed  5mm setting
  9.Back Feed  4mm setting
 10.Back Feed  3mm setting
 11.Compression default setting
 12.Compression 75% setting
 13.Compression 50% setting

Read the comments in the script for details on how it is used.

===========================
 6.Release History
===========================
* Mon May 19 2025
- Version 3.17.0
- Added MCL21
- Supported halftoning option with MCL21, MCL32
- Supported ChromeOS (Linux development environment only)

* Mon Jun 24 2024
- Version 3.16.0
- Added BSC10II
- The following Star Printers at End of Support.
  TSP113GT, TSP651

* Thu Feb 22 2024 
- Version 3.15.0
- Support Tear Off Cut with MCL32

* Fri Sep 8 2023
- Version 3.14.0
- Added support the following printer models.
  TSP100IV SK, SK1-41, SK1-41 Presenter, SK5-31 Presenter.

* Tue May 30 2023
- Version 3.13.1
- Fixed a bug : MCL32, Incorrect cut operation when using black mark paper or label paper.

* Fri Mar 31 2023
- Version 3.13.0
- Added mC-Label3
- The following Star Printers at End of Support.
   FVP10, SM-S220i

* Fri Oct 29 2021
- Version 3.12.0
- Added TSP100IV

* Wed Apr 22 2020
- Version 3.11.0
- Added print density +4 (mC-Print3 Series)
- MCP31C and MCP31CB (mC-Print3 Series) are supported

* Mon Dec 9  2019
- Version 3.10.0
- Added SK1 Printers

* Thu Jul 25 2019
- Version 3.9.0
- Added MCP30 Printer (mC-Print3 Series)

* Mon Nov 5  2018
- Version 3.8.0
- Added mC-Sound Function(MCP31)

* Fri Jun 15 2018
- Version 3.7.0
- Added POP10, MCP31, MCP21 and MCP20
- The following Star Printers at End of Support.
   SP500, TSP650, TSP828L, TSP1000, TUP500, TUP900, HSP7000

* Thu Sep 14 2017
- Version 3.6.0a
- Added SoftwareLicenseAgreementAppendix.pdf

* Tue Jun 7 2016
- Version 3.6.0
- Added TSP100III

* Thu Jan 15 2015
- Version 3.5.0
- Added 1500mm paper length .

* Mon Feb 3 2014
- Version 3.4.2
- Fixed bug that cannot print by using cupsfilter command.

* Tue Jan 28 2014
- Version 3.4.1
- Bug fix.
  Fixed bug that it may cause extremely slow printing or data lost when using CUPS drivers
  V3.4.0 or older with Mac OS X 10.9 (Mavericks).

* Fri Dec 14 2012
- Version 3.4.0 release
- Added TSP650II
- Modified File Permission (Mac OS X)

* Fri Feb 25 2011
- Version 3.2.1 release
- Added "cupsSNMPSupplies is False" in PPD file.
- Modified NSB Invalid command sending in only USB interface of Mac OS X.

* Tue Aug 31 2010
- Version 3.2.0 release
- Added dataTreatmentRecoverFromError Function of TSP700II, TSP600 and SP700

* Tue Apr 20 2010
- Version 3.1.1 release
- Added FVP10

* Fri Feb 19 2010
- Version 3.0.2 release
- Added Tips.(TSP100IIU BackFeed script and Vertical Compression script)

* Tue Jun 30 2009
- Version 3.1.0 release
- Added TSP800II

* Wed Oct 15 2008
- Version 3.0.0 release
- Added TUP500

* Sun Mar 23 2008
- Version 2.10.0 release
- Added HSP7000

* Wed Dec 12 2007
- Version 2.9.0 release
- Added TSP100GT

* Mon Dec 3 2007
- Version 2.8.2 release
- Bug fix. Dot-Printer's Print Speed.(SP700, SP500)

* Sun Sep 9 2007
- Version 2.8.1 release
- Modified File Permission (Mac OS X)

* Tue Jun 26 2007
- Version 2.8.0 release
- Added TSP650

* Thu Feb 8 2007
- Version 2.7.0 release
- Added TSP700II

* Fri Dec 1 2006
- Version 2.6.0 release
- Added SP700

* Fri Feb 24 2006
- Version 2.4.0 release
- Added TSP828L

* Fri Aug 19 2005
- Version 2.3.0 release
- Added TSP100

* Mon Feb 14 2005
- Version 2.2.0 release
- Fixed bug - cash drawer setting not working

* Tue Oct 19 2004
- Version 2.1.0 release
- Added TSP1000
- Added USB device ID support to PPD files
- Fixed bug in support of custom page sizes

* Fri Jul 16 2004
- Version 2.0.0 initial release
