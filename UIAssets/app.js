function getUrlVars() {
    var vars = {};
    var parts = window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi,    
    function(m,key,value) {
      vars[key] = value;
    });
    return vars;
}

window.APIC_DEV_COOKIE = Ext.util.Cookies.get("app_Cisco_EpgInfo_token");
window.APIC_URL_TOKEN =  Ext.util.Cookies.get("app_Cisco_EpgInfo_urlToken");
