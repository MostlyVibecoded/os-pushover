<script>
    $( document ).ready(function() {
        var conditionalFields = [
            ['pushover\\.general\\.NotifyWireGuard', 'pushover\\.general\\.WireGuardThreshold', 'threshold:', 'sec'],
            ['pushover\\.general\\.NotifyOpenVPN',   'pushover\\.general\\.OpenVPNThreshold',   'threshold:', 'sec'],
            ['pushover\\.general\\.NotifyCPUTemp',   'pushover\\.general\\.CPUTempThreshold',   'alert at:',  '°C'],
            ['pushover\\.general\\.NotifyFan',       'pushover\\.general\\.FanThreshold',       'threshold:', 'sec'],
        ];

        function updateConditionalFields() {
            conditionalFields.forEach(function(pair) {
                var checked = $('#' + pair[0]).is(':checked');
                $('#' + pair[1])
                    .prev('span.threshold-label').toggle(checked).end()
                    .toggle(checked)
                    .next('span.threshold-unit').toggle(checked);
            });
        }

        mapDataToFormUI({
            'frm_GeneralSettings': "/api/pushover/settings/get",
            'frm_Monitors':        "/api/pushover/settings/get"
        }).done(function() {
            formatTokenizersUI();
            $('.selectpicker').selectpicker('refresh');

            conditionalFields.forEach(function(pair) {
                var $input = $('#' + pair[1]);
                var $row   = $input.closest('tr');
                var $td    = $('#' + pair[0]).closest('td');
                $('<span class="threshold-label" style="margin-left:10px;color:#888">' + pair[2] + '</span>').appendTo($td);
                $input
                    .css({'width': '70px', 'margin-left': '6px', 'display': 'inline-block'})
                    .appendTo($td)
                    .after('<span class="threshold-unit" style="margin-left:4px;color:#888">' + pair[3] + '</span>');
                $row.remove();
            });

            updateConditionalFields();
        });

        $(document).on('change', 'input[type="checkbox"]', updateConditionalFields);

        $("#saveAct").SimpleActionButton({
            onPreAction: function() {
                const dfObj = new $.Deferred();
                saveFormToEndpoint("/api/pushover/settings/set", 'frm_GeneralSettings', function() {
                    saveFormToEndpoint("/api/pushover/settings/set", 'frm_Monitors', function() {
                        dfObj.resolve();
                    }, false, function() { dfObj.reject(); });
                }, false, function() { dfObj.reject(); });
                return dfObj;
            }
        });

        $("#testAct").click(function() {
            ajaxCall("/api/pushover/service/test", {}, function(data, status) {
                if (status !== "success") {
                    $("#responseMsg")
                        .removeClass('alert-success alert-warning')
                        .addClass('alert-danger')
                        .text("{{ lang._('Request failed. Check your session and try again.') }}")
                        .removeClass('hidden');
                    return;
                }
                if (data && data['status'] === 'ok') {
                    $("#responseMsg")
                        .removeClass('alert-danger alert-warning')
                        .addClass('alert-success')
                        .text("{{ lang._('Test notification sent successfully.') }}")
                        .removeClass('hidden');
                } else {
                    var detail = (data && typeof data['message'] === 'string' && data['message'])
                        ? data['message']
                        : "{{ lang._('unexpected response') }}";
                    // .text() is intentional — do not change to .html(); detail is untrusted server output
                    $("#responseMsg")
                        .removeClass('alert-success alert-warning')
                        .addClass('alert-danger')
                        .text("{{ lang._('Failed to send test notification: ') }}" + detail)
                        .removeClass('hidden');
                }
            });
        });
    });
</script>

<ul class="nav nav-tabs" data-tabs="tabs">
    <li class="active">
        <a href="#tab_config" data-toggle="tab">{{ lang._('Pushover Configuration') }}</a>
    </li>
    <li>
        <a href="#tab_monitors" data-toggle="tab">{{ lang._('Monitors') }}</a>
    </li>
</ul>

<div class="tab-content content-box">
    <div id="tab_config" class="tab-pane fade in active">
        {{ partial("layout_partials/base_form", ['fields': generalForm, 'id': 'frm_GeneralSettings']) }}
    </div>
    <div id="tab_monitors" class="tab-pane fade">
        {{ partial("layout_partials/base_form", ['fields': monitorsForm, 'id': 'frm_Monitors']) }}
    </div>
</div>

<div class="col-md-12">
    <div class="alert hidden" role="alert" id="responseMsg"></div>
</div>

<section class="page-content-main">
    <div class="content-box">
        <div class="col-md-12">
            <br/>
            <button class="btn btn-primary" id="saveAct"
                    data-endpoint='/api/pushover/service/reconfigure'
                    data-label="{{ lang._('Save') }}"
                    data-service-widget="pushover"
                    data-error-title="{{ lang._('Error applying Pushover settings') }}"
                    type="button"
            ></button>
            <button class="btn btn-default" id="testAct" type="button">{{ lang._('Test notification') }}</button>
            <br/><br/>
        </div>
    </div>
</section>
