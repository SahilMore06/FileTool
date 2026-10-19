**PROJECT\
TANGERINE-STYLE**

**PRODUCT REQUIREMENTS DOCUMENT**

A native macOS utility for contextual file conversion,\
editing, compression, and file actions

Version 1.0 \| 19 October 2026\
Status: Proposed / for product and engineering planning

*Reference product: Tangerine for Mac*

# Document Control

  -----------------------------------------------------------------------
  **Field**                           **Details**
  ----------------------------------- -----------------------------------
  Document                            Product Requirements Document (PRD)

  Working product name                Project Tangerine-Style (temporary;
                                      final name to be chosen)

  Version                             1.0

  Date                                19 October 2026

  Status                              Proposed

  Target platform                     macOS on Apple silicon

  Primary interaction                 Contextual radial menu triggered
                                      during file interaction

  Processing model                    Local-first; file content is not
                                      sent to a remote conversion service

  Reference                           https://tangerineformac.com/
  -----------------------------------------------------------------------

## Important scope note

This PRD specifies an independently implemented product inspired by
publicly visible Tangerine for Mac workflows. It does not claim access
to Tangerine\'s source code or private implementation. Product
capabilities referenced here are based on public product pages; the
technical architecture and priorities are proposed design decisions.

# 1. Executive Summary

Project Tangerine-Style is a native macOS productivity utility that
makes file conversion, lightweight editing, compression, and common file
actions available through a contextual interface near the pointer. The
product is intended to reduce application switching and repetitive
navigation for everyday file tasks.

The product combines three capabilities: (1) a contextual interaction
layer, (2) a modular local file-processing engine, and (3) reliable file
actions and output handling. Its differentiator is not any one codec or
editing tool; it is making compatible actions easy to discover and
execute in the user\'s current workflow.

## Product vision

Make common file operations feel like a natural extension of Finder and
the user\'s current workflow.

## Product mission

Reduce the steps required to convert, prepare, organize, and share files
while preserving user control, source files, and privacy.

## Core value proposition

- Contextual: show operations relevant to the current file selection.

- Fast: reduce unnecessary app launches and navigation.

- Local-first: process supported files on the Mac without uploading file
  contents.

- Reliable: validate outputs, preserve originals by default, and explain
  failures.

- Extensible: add format support and tools through modular operation
  adapters.

# 2. Problem Statement

Common file tasks often interrupt a user\'s main activity. A person may
need to open a separate utility, import a file, choose settings, wait
for processing, and then locate the result. Online converters may also
require uploading files to a service. A contextual local utility can
shorten this workflow for supported operations.

## Problems to solve

- Too many steps for simple conversions and edits.

- Repeated switching between Finder and separate utilities.

- Unclear compatibility between file types and operations.

- Risk of accidental overwrite or loss of source files.

- Poor visibility into long-running batch jobs and failures.

- Privacy concerns when files are uploaded to remote services.

## Product hypothesis

If common file operations are available through a consistent contextual
interface, users will complete supported routine file tasks with fewer
steps and less workflow interruption. Validate this hypothesis through
usability testing and task-completion measurements.

# 3. Goals, Non-Goals, and Success Criteria

## 3.1 Goals

- Build a native macOS application with a contextual operation menu.

- Detect file types and show only operations supported by the current
  selection.

- Deliver a dependable MVP for image conversion, compression, and core
  file actions.

- Preserve source files by default and avoid unsafe output overwrites.

- Support batch operations where the operation is compatible across the
  selection.

- Keep processing local and support offline use for all core MVP
  operations.

- Provide progress, cancellation where feasible, and actionable error
  messages.

- Use modular adapters so new formats and tools can be added without
  redesigning the UI.

## 3.2 Non-goals for MVP

- Replacing professional-grade image, video, audio, or office software.

- Supporting every file format or every conversion direction at launch.

- Requiring a cloud account or remote processing service.

- Launching Windows or Linux versions before macOS workflows are
  validated.

- Implementing AI features before the core file workflows are reliable.

- Copying proprietary code, branding, assets, or undisclosed
  implementation details from the reference product.

## 3.3 Success metrics

  -----------------------------------------------------------------------
  **Metric**              **Proposed target**     **Measurement method**
  ----------------------- ----------------------- -----------------------
  Menu responsiveness     Target: menu appears    Instrumented timing on
                          within 150 ms after     supported Macs
                          required interaction    
                          and file data are       
                          available, under        
                          defined test conditions 

  Successful MVP jobs     At least 99% success on Automated integration
                          the agreed valid-file   tests
                          fixture suite           

  Source preservation     100% of tested          Hash and metadata
                          conversions leave       comparisons
                          source files unchanged  

  Output validity         100% of jobs marked     Format-specific
                          successful pass         validation tests
                          relevant output         
                          validation              

  Offline support         All declared MVP        Network-disabled
                          operations work without acceptance tests
                          internet                

  Usability               Users can complete core Moderated usability
                          tasks without coaching  tests
                          after onboarding        

  Crash-free sessions     Target set after beta   Crash diagnostics with
                          baseline; track weekly  privacy-safe telemetry
                                                  if enabled
  -----------------------------------------------------------------------

Targets are proposed engineering goals, not measured claims about
Tangerine.

# 4. Target Users and Use Cases

  -----------------------------------------------------------------------
  **Persona**             **Needs**               **Representative
                                                  tasks**
  ----------------------- ----------------------- -----------------------
  Student                 Prepare assignment      Convert images,
                          assets and documents    compress files, merge
                                                  PDFs, create PDFs from
                                                  images

  Developer               Move quickly between    Copy paths, open a
                          files and tools         containing folder in
                                                  Terminal, archive
                                                  files, batch-convert
                                                  assets

  Designer                Prepare visual assets   Resize, compress, crop,
                          without launching a     annotate, add
                          large editor            backgrounds, create
                                                  collages

  Content creator         Perform lightweight     Trim clips, extract
                          media preparation       frames/audio, normalize
                                                  audio, convert formats

  Privacy-conscious       Process sensitive files Convert locally, remove
  professional            with user control       metadata, redact
                                                  content, work offline
  -----------------------------------------------------------------------

## Primary use cases

- Convert one or more compatible files to a selected output format.

- Compress an image or file while preserving the original.

- Apply a lightweight edit and export a new copy.

- Run a file action such as Copy Path, Copy, Move, AirDrop, Float, or
  open in Terminal.

- Inspect progress, cancel an operation when supported, and locate the
  result.

- Handle mixed selections by clearly identifying unsupported items.

# 5. Product Experience and Interaction Model

## 5.1 Main interaction

Proposed reference interaction: the user begins dragging a file or
selection, presses a configured modifier key to open a contextual
operation wheel, chooses an operation, and drops or confirms the
selection to run it. The reference product publicly describes Shift for
conversion, Command for tools, and Control for file actions; the new
product should validate these mappings and allow configurable shortcuts.

  -----------------------------------------------------------------------
  **Mode**                **Default trigger       **Purpose**
                          proposal**              
  ----------------------- ----------------------- -----------------------
  Convert                 Shift during drag       Choose a compatible
                                                  output format

  Tools                   Command during drag     Show file-specific
                                                  editing and processing
                                                  tools

  Actions                 Control during drag     Show general file
                                                  actions
  -----------------------------------------------------------------------

## 5.2 Interaction states

  -----------------------------------------------------------------------
  **State**                           **Description**
  ----------------------------------- -----------------------------------
  Idle                                No active file interaction

  Drag detected                       Potential file selection detected

  Inspecting                          Resolve file type, permissions, and
                                      capabilities

  Menu open                           Display compatible operations near
                                      the pointer

  Operation selected                  User selects an action

  Validating                          Check inputs, settings,
                                      destination, and output path

  Queued / Running                    Job is scheduled or being processed

  Verifying                           Validate output before finalizing

  Completed                           Show result and destination

  Failed                              Explain failure and provide
                                      recovery options

  Cancelled                           Stop safely and clean temporary
                                      artifacts
  -----------------------------------------------------------------------

## 5.3 Interaction requirements

- The menu should remain stable as the pointer moves between options.

- The menu must adapt to screen edges, display scaling, and multiple
  monitors.

- Only compatible operations should be enabled for the current
  selection.

- Escape should cancel; keyboard navigation should be supported.

- Modifier changes must not trigger unintended operations.

- The menu must not block the main UI thread.

- If a system-wide drag workflow cannot be implemented reliably with
  supported APIs, provide a documented fallback interaction rather than
  shipping fragile behaviour.

# 6. Functional Scope and Priorities

Priority definitions: P0 = required for first usable MVP; P1 = next
expansion; P2 = advanced or later-stage feature.

  -----------------------------------------------------------------------
  **ID**                  **Requirement**         **Priority**
  ----------------------- ----------------------- -----------------------
  FR-001                  Detect eligible file    P0
                          and folder selections   

  FR-002                  Inspect file type and   P0
                          basic metadata          

  FR-003                  Resolve compatible      P0
                          operations for a        
                          selection               

  FR-004                  Display contextual      P0
                          operation menu          

  FR-005                  Convert common          P0
                          supported image formats 

  FR-006                  Resize and compress     P0
                          images                  

  FR-007                  Create a PDF from       P0
                          selected images         

  FR-008                  Copy file paths         P0

  FR-009                  Move files to a         P0
                          user-selected           
                          destination             

  FR-010                  Preserve originals and  P0
                          handle name collisions  
                          safely                  

  FR-011                  Show job status,        P0
                          progress, and errors    

  FR-012                  Support compatible      P0
                          batch image operations  

  FR-013                  Open a file\'s          P0
                          containing folder in    
                          Finder                  

  FR-014                  Merge PDFs and organize P1
                          pages                   

  FR-015                  Add image crop and      P1
                          annotation              

  FR-016                  Inspect, edit, and      P1
                          remove supported        
                          metadata                

  FR-017                  Convert supported audio P1
                          formats                 

  FR-018                  Convert supported video P1
                          formats                 

  FR-019                  Trim audio/video and    P1
                          export video frames     

  FR-020                  Add document and        P1
                          spreadsheet conversions 

  FR-021                  Add archive             P1
                          create/extract with     
                          safe path validation    

  FR-022                  Add a floating file     P1
                          shelf                   

  FR-023                  Add image backgrounds   P2
                          and collages            

  FR-024                  Add video joining,      P2
                          splitting, speed        
                          change, and redaction   

  FR-025                  Add audio               P2
                          normalization, channel  
                          conversion, and         
                          bleeping                

  FR-026                  Add advanced format     P2
                          coverage and            
                          configurable workflows  
  -----------------------------------------------------------------------

# 7. Detailed User Stories and Acceptance Criteria

## US-01: Convert an image

- Given a supported image, the menu shows compatible output formats.

- When the user chooses a format, the app validates the input and
  destination.

- The output is encoded in the selected format, not merely renamed.

- The source remains unchanged and output validity is checked.

- If the output name exists, the app follows the configured collision
  policy.

## US-02: Batch convert files

- The app identifies shared operations across selected files.

- Unsupported files are reported instead of silently skipped.

- Each output is mapped to its source in the job results.

- Partial success and failure are shown clearly.

## US-03: Compress an image

- The user can select a preset, quality level, percentage reduction, or
  target size when feasible.

- The app reports when a target cannot be met without unacceptable
  quality loss.

- The source is preserved and the output dimensions and file size are
  displayed.

## US-04: Copy Path

- The full path is copied to the clipboard as text.

- Multiple paths are copied one per line in a documented order.

- Spaces and Unicode characters are preserved.

- The action works even when no conversion adapter supports the file.

## US-05: Cancel a job

- A long-running job has a visible active state and cancellation
  control.

- Cancellation is honoured when safe and supported by the processing
  engine.

- Temporary artifacts are cleaned up.

- Incomplete outputs are never presented as successful results.

## US-06: Remove metadata

- The UI lists supported metadata categories and the intended removal
  scope.

- The exported artifact is inspected to verify that requested metadata
  was removed.

- The original remains unchanged.

## US-07: Redact sensitive content

- The user can place and adjust redaction regions.

- The export permanently applies redaction to the rendered content.

- Tests verify that covered content is not recoverable from the exported
  artifact.

- For PDFs, overlays alone are not accepted as secure redaction.

## US-08: Work offline

- Core declared MVP operations run without network access.

- No remote conversion API is required.

- Optional licensing or update checks, if added, are separated from file
  processing and documented.

# 8. Supported File Categories and Expansion Plan

Format support must be defined as explicit input/output pairs. A format
being readable does not imply every conversion direction is supported.
The initial release should prioritize a small, well-tested matrix.

  -----------------------------------------------------------------------
  **Category**            **MVP**                 **Later expansion**
  ----------------------- ----------------------- -----------------------
  Images                  JPEG, PNG, HEIC input   WebP, TIFF, AVIF, BMP,
                          where supported;        SVG input, crop,
                          PNG/JPEG export;        annotate, backgrounds,
                          resize/compress;        collage, redaction
                          images-to-PDF           

  PDF                     Create PDF from images  Render pages to images,
                                                  merge, reorder, rotate,
                                                  duplicate, remove
                                                  pages, text extraction

  Audio                   Not required for MVP    MP3, M4A, WAV, FLAC,
                                                  OGG, Opus, AIFF; trim,
                                                  normalize, channels

  Video                   Not required for MVP    MP4, MOV, MKV, WebM,
                                                  AVI, WMV, GIF; trim,
                                                  crop, speed, frames,
                                                  split/join

  Documents               Not required for MVP    DOCX, Pages, Markdown,
                                                  TXT, EPUB; HTML export
                                                  and supported
                                                  conversions

  Slides                  Not required for MVP    PPT/PPTX to PDF or
                                                  images; PDF-to-PPTX
                                                  where quality is
                                                  acceptable

  Spreadsheets            Not required for MVP    XLSX, ODS, CSV, TSV;
                                                  PDF export and
                                                  documented feature
                                                  limitations

  Subtitles               Not required for MVP    SRT/VTT conversion and
                                                  TXT export

  Archives                Not required for MVP    ZIP/TAR/GZIP creation
                                                  and extraction; RAR
                                                  input only if supported
                                                  by chosen library
  -----------------------------------------------------------------------

All format claims must be tested against the actual chosen processing
libraries and their build configurations.

# 9. Technical Architecture (Proposed)

Recommended implementation: Swift with SwiftUI and AppKit for the native
macOS shell, using Apple frameworks for supported media operations and
maintained third-party engines where needed. This is a proposed
architecture, not a statement about Tangerine\'s private implementation.

  -----------------------------------------------------------------------
  **Module**                          **Responsibilities**
  ----------------------------------- -----------------------------------
  App shell                           Lifecycle, menu-bar presence,
                                      settings, permissions, app state

  Interaction coordinator             Drag/keyboard state machine,
                                      modifier mapping, screen coordinate
                                      handling

  Contextual UI                       Radial menu, operation
                                      highlighting, keyboard navigation,
                                      accessibility

  File inspector                      File URLs, type detection, basic
                                      metadata, readability and
                                      permission checks

  Capability registry                 Resolve valid operations and output
                                      types for selected inputs

  Operation planner                   Validate configuration,
                                      destination, output path, and
                                      resource needs

  Job orchestrator                    Queue, schedule, report progress,
                                      cancel, and collect results

  Processing adapters                 Image, audio, video, PDF, document,
                                      archive, subtitle, and metadata
                                      engines

  Safe output writer                  Temporary output, validation,
                                      collision handling, atomic
                                      finalization where possible

  File actions                        Copy, Move, Copy Path,
                                      AirDrop/share, Float shelf,
                                      Terminal integration

  Preferences/history                 User settings and optional local
                                      job history

  Security layer                      Permission boundaries, safe archive
                                      extraction, temporary-file cleanup,
                                      privacy-safe logs
  -----------------------------------------------------------------------

## 9.1 Suggested technology choices

  ------------------------------------------------------------------------
  **Need**                **Candidate             **Notes**
                          technology**            
  ----------------------- ----------------------- ------------------------
  Native UI               SwiftUI + AppKit        SwiftUI for standard UI;
                                                  AppKit for advanced
                                                  macOS integration

  Image I/O               Core Graphics and Image Use native formats and
                          I/O                     validate output

  Audio/video             AVFoundation and/or     Choose based on required
                          FFmpeg                  format coverage and
                                                  distribution/licensing
                                                  review

  PDF                     PDFKit and Core         Validate page rendering
                          Graphics                and output structure

  Office documents        LibreOffice or a        Evaluate quality, size,
                          compatible library      licensing, and bundling
                                                  requirements

  Archives                Foundation APIs and/or  Prevent path traversal
                          maintained archive      and unsafe extraction
                          library                 

  Metadata                Format-specific         Metadata formats differ
                          adapters                by media type

  Local persistence       UserDefaults and/or     Persist only what is
                          SQLite                  needed; do not store
                                                  file contents
  ------------------------------------------------------------------------

## 9.2 Architecture flow

File selection → interaction coordinator → file inspector → capability
registry → operation planner → job orchestrator → processing adapter →
output validator → safe output writer → completion UI.

## 9.3 Capability adapter contract

- Stable operation identifier and display name.

- Supported input types and output types.

- Capability check for a file or selection.

- Typed settings schema and validation.

- Estimated resource needs where practical.

- Execution method with progress and cancellation reporting.

- Output validation method.

- Structured error codes and user-safe messages.

# 10. Data Model

  -----------------------------------------------------------------------
  **Entity**                          **Suggested fields**
  ----------------------------------- -----------------------------------
  FileReference                       id, file URL, filename, extension,
                                      detected type, size, modification
                                      time, readability status

  OperationDefinition                 id, display name, category, input
                                      types, output types, settings
                                      schema, capability predicate

  OperationJob                        id, operation ID, input references,
                                      output directory, configuration,
                                      status, progress, timestamps, error
                                      code

  OutputArtifact                      id, job ID, output URL, detected
                                      type, size, validation status

  UserPreferences                     shortcut mappings, output location,
                                      collision policy, default quality
                                      settings, notifications, privacy
                                      preferences
  -----------------------------------------------------------------------

Use strongly typed Swift models. Persist only preferences and optional
job history that materially improve the product. Avoid storing file
contents in the application database.

# 11. Privacy, Security, and Data Handling

## 11.1 Privacy requirements

- Core file processing must not upload file contents to a remote
  conversion service.

- Core MVP operations must work offline.

- Do not transmit file paths, contents, or sensitive metadata
  unnecessarily.

- Keep logs free of file contents and unnecessary personal information.

- Remove temporary files when no longer needed.

- Clearly disclose any optional network use such as updates or license
  verification.

- Request filesystem or accessibility permissions only when necessary
  and explain why.

- Provide a privacy-safe error-reporting design; sensitive diagnostics
  must not be sent automatically.

## 11.2 Security requirements

- Validate file types and malformed inputs before processing.

- Avoid shell command construction from untrusted filenames.

- Pass external-process arguments safely.

- Prevent archive path traversal and extraction outside the chosen
  destination.

- Handle symbolic links and filesystem permissions carefully.

- Use bounded resource consumption for large or malformed files.

- Prevent accidental overwrite of source files.

- Validate output before reporting success.

- Treat redaction as irreversible content removal, not merely a visual
  overlay.

# 12. Non-Functional Requirements

  -----------------------------------------------------------------------
  **Area**                            **Requirement**
  ----------------------------------- -----------------------------------
  Performance                         Menu and file inspection should be
                                      responsive; define and benchmark
                                      targets on actual supported Macs.

  Responsiveness                      Long-running work must not block
                                      the main UI thread.

  Reliability                         Failures must not silently corrupt
                                      or replace original files.

  Compatibility                       Define and test supported macOS
                                      versions and Apple silicon models.

  Accessibility                       Support keyboard navigation,
                                      accessible labels, and clear focus
                                      indication.

  Maintainability                     Keep processing engines behind
                                      stable adapters.

  Extensibility                       Add formats without rewriting the
                                      menu or job system.

  Resource management                 Use bounded concurrency for memory-
                                      and CPU-intensive jobs.

  Observability                       Capture actionable, privacy-safe
                                      error codes and job states.

  Recovery                            Interrupted jobs must not leave
                                      misleading successful outputs.

  Localization                        Keep user-facing strings
                                      externalizable for future
                                      localization.
  -----------------------------------------------------------------------

# 13. Error Handling

  -----------------------------------------------------------------------
  **Error condition**                 **Expected behaviour**
  ----------------------------------- -----------------------------------
  Unsupported format                  Explain that no compatible
                                      operation is available; keep
                                      general file actions available.

  Unreadable or corrupted file        Show a concise error and avoid
                                      creating a successful-looking
                                      output.

  Permission denied                   Explain which permission or
                                      destination is unavailable and
                                      provide a user-authorized recovery
                                      path.

  Insufficient disk space             Stop safely when possible and
                                      preserve the original.

  Output filename exists              Apply a clear policy: ask, rename,
                                      or cancel; never silently overwrite
                                      by default.

  Processing engine fails             Capture a structured error, clean
                                      temporary output, and offer retry
                                      where useful.

  User cancels                        Stop safely, remove temporary
                                      artifacts, and mark the job
                                      cancelled.

  Partial batch failure               Show per-file success/failure and
                                      identify outputs created.

  Unsupported codec                   Explain codec limitation separately
                                      from file extension.
  -----------------------------------------------------------------------

# 14. Development Roadmap

  -----------------------------------------------------------------------
  **Phase**               **Focus**               **Deliverable / exit
                                                  criterion**
  ----------------------- ----------------------- -----------------------
  0\. Feasibility spike   Finder drag detection,  Verified implementation
                          modifier keys, screen   path or documented
                          positioning,            fallback for the
                          permissions,            defining interaction
                          multi-monitor testing   

  1\. Core shell          Native app, menu, file  Stable interaction
                          inspector, capability   prototype and unit
                          registry, settings      tests

  2\. MVP processing      Image conversion,       End-to-end local
                          resizing, compression,  workflow with safe
                          image-to-PDF, Copy      output handling
                          Path, Move              

  3\. Reliability         Job queue, progress,    MVP acceptance suite
                          cancellation,           passes
                          validation, batch       
                          operations, offline     
                          tests                   

  4\. PDF and image tools Merge/reorder PDFs,     Expanded utility beta
                          crop, annotate,         
                          metadata inspection     

  5\. Media and documents Audio/video, documents, Feature-by-feature
                          spreadsheets,           validated format matrix
                          subtitles, archives     

  6\. Advanced tools      Redaction, collages,    Advanced functionality
                          visualizers, floating   with security and
                          shelf, advanced editing usability validation

  7\. Release engineering Dependency licences,    Release candidate
                          signing, packaging,     
                          compatibility,          
                          documentation, beta     
                          feedback                
  -----------------------------------------------------------------------

## Recommended build order

Do not begin by implementing every conversion path. First prove the
system-level interaction, then complete one vertical slice: select file
→ show contextual menu → convert image → validate output → reveal
result. This exposes the highest-risk technical assumptions early.

# 15. Testing and Quality Plan

## 15.1 Unit tests

- File-type detection and capability resolution.

- Output naming and collision policies.

- Operation configuration validation.

- Progress and job state transitions.

- Metadata parsing and removal.

- Subtitle timestamp parsing if included.

- Archive path validation if archive support is included.

## 15.2 Integration tests

- Run each supported input/output pair through the actual processing
  engine.

- Validate the resulting file using an independent parser or decoder
  where possible.

- Verify source files remain unchanged.

- Verify cancellation and cleanup.

- Verify partial batch failures are represented accurately.

- Run core operations with network disabled.

## 15.3 UI and system tests

- Modifier-key changes and menu dismissal.

- Keyboard navigation and Escape cancellation.

- Screen-edge and multi-monitor positioning.

- Finder-originated drags and documented fallback behaviour.

- Permission denial and recovery.

- Accessibility labels and focus handling.

- Large file and large selection responsiveness.

## 15.4 Test fixture set

Maintain a versioned fixture suite containing small and large
JPEG/PNG/HEIC images, transparency, EXIF metadata, animated images,
videos with and without audio, multiple audio codecs, text and scanned
PDFs, documents with tables, multi-sheet spreadsheets, valid and
malformed archives, and SRT/VTT subtitles as applicable to implemented
features.

# 16. Risks and Mitigations

  -----------------------------------------------------------------------
  **Risk**                **Severity**            **Mitigation**
  ----------------------- ----------------------- -----------------------
  System-wide drag        Critical                Prototype in Phase 0;
  interaction is not                              validate before
  reliable through                                committing to full
  supported APIs                                  scope

  Modifier events behave  High                    Test on supported macOS
  inconsistently across                           versions and document
  apps                                            fallback

  Conversion output loses High                    Define quality
  formatting or fidelity                          expectations per
                                                  operation and test
                                                  representative files

  Large media jobs        High                    Streaming, bounded
  exhaust resources                               concurrency,
                                                  cancellation, resource
                                                  limits

  Output corruption       High                    Temporary files, format
                                                  validation, safe
                                                  finalization

  Redaction leaves data   Critical                Validate exported
  recoverable                                     artifacts and use true
                                                  content removal

  Archive extraction      High                    Normalize and validate
  escapes target                                  paths before extraction
  directory                                       

  Third-party licence     High                    Audit licences and
  conflicts                                       bundled build
                                                  configuration before
                                                  distribution

  Feature scope becomes   High                    Enforce MVP boundary
  too large                                       and ship in phases

  Permission prompts      Medium                  Request permissions
  confuse users                                   contextually and
                                                  explain purpose
  -----------------------------------------------------------------------

# 17. MVP Definition of Done

The MVP is ready for external testing when a user can:

1.  Select a supported file using the intended interaction or documented
    fallback.

2.  Open a contextual menu reliably.

3.  See only compatible operations.

4.  Convert or compress a supported image locally.

5.  Create a PDF from selected images.

6.  Copy file paths and move files using explicit user intent.

7.  See progress and actionable errors.

8.  Cancel supported long-running jobs safely.

9.  Handle output filename collisions without silent overwrite.

10. Complete declared core operations with the network disabled.

11. Verify that the source file remains unchanged after conversion.

Release is blocked by any unresolved critical data-loss, privacy, unsafe
archive, or redaction defect in a feature included in the release.

# 18. Distribution and Business Model (Decision Required)

Potential options include a time-limited trial with one-time purchase, a
free basic tier with a paid upgrade, or a paid application with optional
future upgrades. The pricing model should be chosen after validating
user demand, development costs, App Store distribution constraints, and
willingness to pay.

  -----------------------------------------------------------------------
  **Option**              **Benefits**            **Trade-offs**
  ----------------------- ----------------------- -----------------------
  Free trial + one-time   Easy to understand;     Requires licensing and
  purchase                supports evaluation     trial implementation

  Free basic + paid       Low-friction adoption   Requires a clear
  upgrade                                         feature boundary

  Paid application        Simple product          Higher barrier to first
                          proposition             use

  Subscription            Recurring revenue       May be difficult to
                                                  justify for a
                                                  lightweight utility
  -----------------------------------------------------------------------

No pricing decision is locked by this PRD.

# 19. Open Questions / Decisions Needed

- Can the desired Finder-originated drag and modifier-key workflow be
  implemented reliably with supported APIs on the target macOS versions?

- What is the minimum supported macOS version after feasibility and
  framework checks?

- Which exact image formats and conversion directions are in the MVP?

- Should the app be distributed through the Mac App Store, direct
  download, or both?

- Will optional telemetry be included? If yes, what is the opt-in and
  data-retention policy?

- Which media engine and build configuration meet functionality and
  licensing requirements?

- What is the default output location and collision policy?

- Should job history be persisted, and for how long?

- What keyboard shortcuts are configurable?

- What trial and pricing model will be tested?

# 20. Reference Research and Sources

Public product research was used to understand the reference product\'s
advertised workflow and capabilities. The technical architecture, MVP
priorities, data models, success metrics, and implementation
recommendations in this PRD are original proposals.

- **Tangerine official website --- core workflow, conversion categories,
  file actions, and local-processing claims:**
  https://www.tangerineformac.com/

- **Tangerine file tools --- publicly described image, video, audio, and
  PDF tools:** https://www.tangerineformac.com/tools

- **Tangerine press kit --- public product details and feature
  summary:** https://www.tangerineformac.com/press

- **Tangerine Mac App Store listing --- advertised capabilities and
  purchase experience:**
  https://apps.apple.com/us/app/tangerine-file-converter/id6813034065?mt=12

- **Apple AppKit drag-and-drop documentation:**
  https://developer.apple.com/documentation/AppKit/drag-and-drop

- **Apple AppKit event handling documentation:**
  https://developer.apple.com/documentation/appkit/event-handling

- **Apple SwiftUI documentation:**
  https://developer.apple.com/documentation/swiftui

# Appendix A --- Suggested Initial Repository Structure

ProjectTangerine/\
App/\
Interaction/\
DragInteractionCoordinator.swift\
KeyboardShortcutManager.swift\
InteractionStateMachine.swift\
ScreenCoordinateMapper.swift\
UI/\
RadialMenu/\
ConversionMenu/\
ToolsMenu/\
ActionsMenu/\
Progress/\
Settings/\
FileInspection/\
FileInspector.swift\
FileTypeDetector.swift\
CapabilityResolver.swift\
Operations/\
OperationProtocol.swift\
OperationRegistry.swift\
OperationPlanner.swift\
OperationValidator.swift\
JobSystem/\
JobCoordinator.swift\
JobScheduler.swift\
CancellationManager.swift\
Engines/\
ImageEngine/\
PDFEngine/\
AudioEngine/\
VideoEngine/\
DocumentEngine/\
ArchiveEngine/\
MetadataEngine/\
FileActions/\
Storage/\
Security/\
Tests/\
UnitTests/\
IntegrationTests/\
UIAutomationTests/\
FileFixtureTests/

# Appendix B --- One-Sentence Product Definition

**A native, local-first macOS utility that brings compatible file
conversions, lightweight editing tools, and everyday file actions to a
contextual interface near the user\'s pointer.**
