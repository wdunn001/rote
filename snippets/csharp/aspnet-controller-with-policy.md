---
slug: aspnet-controller-with-policy
name: ASP.NET controller with permission policy
language: csharp
applies_patterns: service-layer
applies_technologies: 
references: 
---

# When to use
New REST endpoint in Acme where authorization is permission-based
(not just authenticated).  Uses the Policy attribute matching
AuthorizationExtensions.Policy enum + delegates to an AppService.

# When NOT to use
Public endpoint (no auth) — use [AllowAnonymous].

The work belongs in the Worker (queued) — controller should enqueue, not do it.

# Placeholders
- CONTROLLER_NAME: controller class name (example: DroneCommandsController)
- ROUTE_PREFIX: URL prefix (example: drones)
- ENDPOINT_NAME: action method name (example: Issue)
- VERB_PATH: URL suffix (example: {droneId}/commands)
- HTTP_METHOD: HTTP method attribute (example: HttpPost)
- POLICY_NAME: policy enum value (example: DronesControl)
- APP_SERVICE: the app service field type (example: IDroneCommandAppService)
- APP_SERVICE_VAR: the field name (example: _droneCommands)
- REQUEST_DTO: request body DTO type (example: IssueDroneCommandRequest)

# Snippet
```csharp
[ApiController]
[Route("api/v1/${ROUTE_PREFIX}")]
public class ${CONTROLLER_NAME} : ControllerBase {
    private readonly ${APP_SERVICE} ${APP_SERVICE_VAR};
    public ${CONTROLLER_NAME}(${APP_SERVICE} svc) => ${APP_SERVICE_VAR} = svc;

    [${HTTP_METHOD}("${VERB_PATH}")]
    [Authorize(Policy = nameof(AuthorizationExtensions.Policy.${POLICY_NAME}))]
    public async Task<IActionResult> ${ENDPOINT_NAME}(
        [FromRoute] DroneId droneId,
        [FromBody] ${REQUEST_DTO} req,
        CancellationToken ct
    ) {
        var result = await ${APP_SERVICE_VAR}.${ENDPOINT_NAME}Async(droneId, req, ct);
        return result switch {
            { Status: "denied", Reason: var r } => Forbid(r),
            { Status: "accepted" }              => Accepted(result),
            _                                   => BadRequest(result)
        };
    }
}
```

# Example expansion
See DroneCommandsController, FleetCommandsController in example-app.
