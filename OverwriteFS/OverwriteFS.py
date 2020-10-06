###########################################################################
# Update / Overwrite Feature Service                                      #
# By: Deniz Karagulle & Paul Dodd, Software Product Release, Esri         #
#                                                                         #
# v1.0.0, Jan 2019 - Released                                             #
# v1.1.0, Jan 2019 - Added support for 'Touching' views related to FS.    #
# v1.2.0, Feb 2019 - Updated to run Standalone or be leveraged via Import.#
# v1.3.0, Feb 2019 - Updated to support URL download.                     #
# v1.4.0, Feb 2019 - Updated to better handle SSL Context. Save download  #
#                    to temp folder when url is used. Open url prior to   #
#                    downloading, to execute faster Last Modified check!  #
#                    Compare url data Last Modified to Service Layer Last #
#                    Modified, skip if not newer. Improved reporting.     #
# v1.4.1, Mar 2019 - Patched Last Service Edit date logic to handle 'None'#
#                    Added Elapsed Time to Overwrite results.             #
# v1.4.2, Apr 2020 - Added connection password validation, avoid password #
#                    prompt if password is missing or null.               #
# v1.4.3, May 2020 - Added log in option to leverage ArcGIS Pro account.  #
# v1.4.4, Jul 2020 - Corrected Url Header access issue during downloads.  #
###########################################################################

import os, sys, datetime, tempfile
import configparser
import urllib.request

if not __name__ == "__main__":
    # Make sure arcgis module is loaded if import
    import arcgis

def overwriteFeatureService( item, updateFile=None, touchItems=True, verbose=False):
    """Function: overwriteFeatureService( <item>[, <updateFile>[, <touchItems>[, <verbose>]]])

Overwrites an Existing Feature Service with new Data matching Schema of data used during initial Publication.

If updateFile is not included, this function will only touch the Service item to update its last modified date.

* Note * If Views have been created that reference the Service, this function will also touch the View items to update
their last mondified date.

Returns Dictionary containing update success status and an Item list of Items altered and their status.

Or

Exception is raised when a critial obsticle is reached.

          <item>: (required) The Hosted Feature Service 'arcgis.gis.item' object you wish to update.

    <updateFile>: (optional) The File Path and/or Name of the file, or URL, to overwrite Service data with.
                             Default: None, only 'Touch' the Feature Service Item if allowed.

    <touchItems>: (optional) 'Touch' Feature Service Item (if no <updateFile>) and related Views, to refresh last modified date?
                             Default: True

       <verbose>: (optional) Display progress actions and results?
                             Default: False, just return results.
"""
    def touchItem( item, message, outcome):
        if verbose:
            print( message)

        status = None
        try:
            status = item.update()
            if not status == True:
                raise Exception( status)

            if verbose:
                print( " - Success!")

        except Exception as e:
            if verbose:
                print( " * Failed to Touch details for Item Id: '{}', Outcome: '{}'".format( item.id, e))
            status = "Failed, Outcome: '{}'".format( e)
            status = status if not "error code" in status.lower() else status.replace( "\n", " ")

        outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "touch", "result": status})
        return (status == True)

    #####################
    # Start of Function #
    #####################

    outcome = { "success": None, "items": []}

    #
    # Verify Item
    #
    if not item.type == "Feature Service":
        outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "verify", "result": "Item Type is NOT a 'Feature Service'"})
        outcome[ "success"] = False     # Set as error
    else:
        #
        # Verify Service Data Item and get original Filename used for publication
        #
        outputFile = ""
        for dataItem in item.related_items( "Service2Data"):
            outputFile = dataItem.name

        if not outputFile:
            outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "verify", "result": "Missing Associated Service Data Item or datafile Item 'name'"})
            outcome[ "success"] = False     # Set as error

            return outcome

        #
        # Do Download and/or Update
        #
        if updateFile:
            #
            # Get Feature Layer Manger for item
            #
            manager = arcgis.features.FeatureLayerCollection.fromitem( item).manager
            layers = manager.properties.get( "layers", [])

            # Get Last Modified details
            serviceLastModified = 0 if not layers else layers[0].get( "editingInfo", {}).get( "lastEditDate", 0)
            serviceLastModified = 0 if not serviceLastModified else datetime.datetime.utcfromtimestamp( int( serviceLastModified / 1000))

            if verbose and serviceLastModified:
                print( " - Service Last Modified: {}".format( serviceLastModified.strftime( "%a, %d %b %Y %H:%M:%S GMT")))

            #
            # Download Web data for update!
            #
            if updateFile.split(":")[0].lower() in ["ftp", "http", "https"]:
                outputFile = os.path.join( tempfile.gettempdir(), outputFile)

                # Get Last Modified details
                fileLastModified = 0 if not os.path.exists( outputFile) else datetime.datetime.utcfromtimestamp( int( os.stat( outputFile).st_mtime))

                # Set lastModified to file lastModified if Service details are not available!
                lastModified = serviceLastModified if serviceLastModified else fileLastModified

                try:
                    authHandlers = []

                    # Add Hander(s)
                    authHandlers.append( urllib.request.HTTPSHandler( context=urllib.request.ssl.SSLContext( urllib.request.ssl.PROTOCOL_SSLv23)))

                    # Install Handler(s)
                    if verbose:
                        print( "\nAccessing URL...")
                    urllib.request.install_opener( urllib.request.build_opener( * authHandlers))

                    request = urllib.request.urlopen( updateFile)
                    headers = dict( request.info()._headers) if hasattr( request, "info") else {}   # Get Header 'Tuple' list and convert to dictionary

                    if verbose:
                        print( " - Download to: '{}', Last Modified: {}".format( outputFile, fileLastModified.strftime( "%a, %d %b %Y %H:%M:%S GMT") if fileLastModified else "N/A"))
                        print( "\nWeb Headers:")
                        for key, value in headers.items():
                            print( " - {}: {}".format( key, value))

                    try:
                        if lastModified and "Last-Modified" in headers and lastModified >= datetime.datetime.strptime( headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S GMT"):
                            status = "No Change in URL Data"
                            if verbose:
                                print( "\n * {}!".format( status))

                            outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "download", "result": status})

                            return outcome

                    except Exception as e:
                        if verbose:
                            print( " * Issue Ignored * But, unable to compare 'Last-Modified' Dates, Error: '{}'".format( e))

                    # Download file!
                    if verbose:
                        print( "\nDownloading Data...")
                    updateFile, headers = urllib.request.urlretrieve( updateFile, outputFile)

                except Exception as e:
                    status = "Failed to Download data from url, Outcome: '{}'".format( e)
                    if verbose:
                        print( " * {}".format( status))

                    outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "download", "result": status})
                    outcome[ "success"] = False     # Set as error

                    return outcome

            elif not os.path.split( updateFile)[-1] == os.path.split( outputFile)[-1]:
                outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "verify", "result": "Update Filename '{}' does NOT match Original Filename used to Publish Service: '{}'".format( updateFile, outputFile)})
                outcome[ "success"] = False     # Set as error

                return outcome

            #
            # Perform Overwrite or Update!
            #
            if verbose:
                print( "\nPerforming Overwrite...")

            status = None
            try:
                start = datetime.datetime.now()
                status = manager.overwrite( updateFile)

                if not (status and isinstance( status, dict) and "success" in status and status[ "success"]):
                    raise Exception( status)

                status = True
                if verbose:
                    print( " - Success! Elapsed Time: {}".format( datetime.datetime.now() - start))

            except Exception as e:
                if verbose:
                    print( " * Failed to Update Item, Id: '{}', Outcome: '{}'".format( item.id, e))
                status = "Failed, Outcome: '{}'".format( e)
                status = status if not "error code" in status.lower() else status.replace( "\n", " ")

            outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": "update", "result": status})
            outcome[ "success"] = (status == True)

        elif touchItems:
            outcome[ "success"] = touchItem( item, "\nTouching Item details...", outcome)

        else:
            outcome[ "items"].append( {"id": item.id, "title": item.title, "itemType": item.type, "action": None, "result": None})

    #
    # Touch related Feature Service Views, if any exist!
    #
    if touchItems and outcome[ "success"] == True:
        for view in item.related_items( "Service2Service"):
            touchItem( view, "\nTouching details for related View: '{}'".format( view.title), outcome)

    return outcome

if __name__ == "__main__":

    version = "v1.4.4"
    #
    # Verify Inputs
    #
    if len( sys.argv) < 4:
        print( "\n{} Usage: Python {} <profile> <item> <title> [<filename>[, <url>]]".format( version, __file__))
        print( "\n   <profile>: (required) Stored Python API user Profile to connect with.")
        print( "              Specify 'Pro' to leverage active ArcGIS Pro connection, also requires Arcpy!")
        print( "      <item>: (required) Id of Feature Service Item to update or touch.")
        print( "     <title>: (required) Title of Item, to verify id matches correct item.")
        print( "  <filename>: (optional) File path and/or name, or URL, to overwrite Service data with.")
        print( "                         Default: None, only touch Item and Views to refresh last update date.")

        exit( "\n\a * ERROR * Insufficient Input Parameters, please review 'Usage'!")

    profile, itemId, itemTitle = sys.argv[1:4]
    updateFile, updateExists = (None, False) if len( sys.argv) < 5 else (sys.argv[4], os.path.exists( sys.argv[4]) if not sys.argv[4].split(":")[0].lower() in ["ftp", "http", "https"] else None)
    fileLastModified = 0 if not updateExists else datetime.datetime.utcfromtimestamp( int( os.stat( updateFile).st_mtime))
    usingPro = profile.lower() == "pro"

    print( "\n           Running: {}, {}".format( __file__, version))
    print( "Python API Profile: {}{}".format( profile, " (using active ArcGIS Pro connection)" if usingPro else ""))
    print( " Target FS Item ID: {}".format( itemId))
    print( " Target Item Title: '{}' (for verification)".format( itemTitle))
    print( "   Upload Filename: {}{}".format( *((updateFile, ", Last Modified: {}".format( fileLastModified.strftime( "%a, %d %b %Y %H:%M:%S GMT"))) if updateExists else (((updateFile, " (NOT Found!)") if updateExists is False else (updateFile, " (From URL!)")) if updateFile and updateExists is None else ("None, Touch item & views only!", "")))))

    if updateFile and updateExists is False:
        exit( "\n\a * ERROR * Unable to locate Update File '{}' *".format( updateFile))

    #
    # Verify Login
    #
    print( "\nLoading Python API...", end="", flush=True)
    import arcgis   # Import Python API
    print( "Ready!\n", flush=True)

    if not usingPro:
        getPassword = None
        if hasattr( arcgis.GIS, "_securely_get_password"):
            # Get password function from GIS object for Python API v1.6.0
            getPassword = arcgis.GIS()._securely_get_password
        elif hasattr( arcgis.gis, "_impl") and hasattr( arcgis.gis._impl, "_profile"):
            # Get password function from Profile Manager for Python API v1.7.0+?
            getPassword = arcgis.gis._impl._profile.ProfileManager()._securely_get_password
        else:
            print( " - Cannot check password for Python API v{}, unable to securely get password!".format( arcgis.__version__))

        if getPassword:
            # Check Profile Password
            gis_cfg_file_path = os.path.expanduser("~") + '/.arcgisprofile'
            if os.path.isfile( gis_cfg_file_path) and profile: # v1.5.0
                # Load config, get username form Profile
                gisConfig = configparser.ConfigParser()
                gisConfig.read( gis_cfg_file_path)
                username = gisConfig[ profile][ "username"] if gisConfig.has_option( profile, "username") else None

                # Verify we have a password for username, to avoid password prompt!
                if username is not None and username:
                    if getPassword( profile) is None:
                        exit( "\n\a * ERROR * Password missing for user '{}' in Profile '{}'!".format( username, profile))

            print("Accessing ArcGIS Online/Enterprise...")
            gis = arcgis.GIS( profile=profile)	# Be sure your Profile exists!

            if not gis._username:
                exit( "\n\a * ERROR * Login failed, please verify Profile!")
    else:
        print("Accessing ArcGIS Online/Enterprise using Pro...")
        gis = arcgis.GIS( "pro")	# Be sure your Profile exists!
        print( " - Logged in with user: '{} ({})', On: '{}'".format( gis.users.me.username, gis.users.me.fullName, gis.url))

    #
    # Verify Item
    #
    print( " - Checking item...")

    item = gis.content.get( itemId)
    if not item:
        exit( "\a * ERROR * Unable to Locate specified Item: {} *".format( itemId))

    if not item.title == itemTitle:
        exit( "\a * ERROR * Feature Service Item Title does NOT match specified Title: '{}', Found: '{}'".format( itemTitle, item.title))

    #
    # Perform Overwrite or Touch Item!
    #
    outcome = overwriteFeatureService( item, updateFile, verbose=True)
    if outcome[ "success"] == False:
        exit( "\n\a * ERROR * " + outcome[ "items"][0][ "result"])