let wait = 60;

// Countdown function to manage resend button timing
function time(o) {
    if (wait == 0) {
        o.removeAttribute("disabled");
        o.value = "Get verification code";
        wait = 60;
        return false;
    } else {
        o.setAttribute("disabled", true);
        o.value = "Resend (" + wait + ")";
        wait--;
        setTimeout(function () {
            time(o);
        }, 1000);
    }
}

// Event triggered when the send button is clicked
document.getElementById("btn").onclick = function () {
    let id_email = $("#id_email");
    let token = $("*[name='csrfmiddlewaretoken']").val();
    let ts = this;
    let myErr = $("#myErr");

    $.ajax({
        url: "/forget_password_code/",
        type: "POST",
        data: {
            "email": id_email.val(),
            "csrfmiddlewaretoken": token
        },
        success: function (result) {
            if (result != "ok") {
                myErr.remove();
                id_email.after("<ul class='errorlist' id='myErr'><li>" + result + "</li></ul>");
                return;
            }
            myErr.remove();
            time(ts);
        },
        error: function (e) {
            alert("Failed to send, please try again");
        }
    });
}
