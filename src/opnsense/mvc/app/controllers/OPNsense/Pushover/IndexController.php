<?php

namespace OPNsense\Pushover;

class IndexController extends \OPNsense\Base\IndexController
{
    public function indexAction()
    {
        $this->view->generalForm  = $this->getForm("general");
        $this->view->monitorsForm = $this->getForm("monitors");
        $this->view->pick('OPNsense/Pushover/index');
    }
}
