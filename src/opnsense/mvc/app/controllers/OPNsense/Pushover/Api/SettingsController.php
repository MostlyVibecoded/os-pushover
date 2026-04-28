<?php

namespace OPNsense\Pushover\Api;

use OPNsense\Base\ApiMutableModelControllerBase;

class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelClass = 'OPNsense\Pushover\Pushover';
    protected static $internalModelName = 'pushover';
}
