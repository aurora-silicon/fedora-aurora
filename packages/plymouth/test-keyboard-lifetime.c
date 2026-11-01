/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Copyright (C) 2026 Ryan Murray */
/* Compile with the prepared source directory in the include path. Including
 * the device manager exposes its real renderer-removal path without udev or
 * a physical GPU. Xvfb supplies the initial pixel display and keyboard.
 */
#include "config.h"
#include "ply-device-manager.c"
#include "ply-boot-splash.h"

#define CHECK(condition) do { \
        if (!(condition)) { \
                fprintf (stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); \
                exit (EXIT_FAILURE); \
        } \
} while (0)

typedef struct {
        ply_boot_splash_t *splash;
        unsigned int keyboards_added;
        unsigned int keyboards_removed;
} context_t;

static void
keyboard_added (context_t *context, ply_keyboard_t *keyboard)
{
        context->keyboards_added++;
        ply_boot_splash_set_keyboard (context->splash, keyboard);
}

static void
keyboard_removed (context_t *context, ply_keyboard_t *keyboard)
{
        context->keyboards_removed++;
        ply_boot_splash_unset_keyboard (context->splash);
}

static void
pixel_added (context_t *context, ply_pixel_display_t *display)
{
        ply_boot_splash_add_pixel_display (context->splash, display);
}

static void
pixel_removed (context_t *context, ply_pixel_display_t *display)
{
        ply_boot_splash_remove_pixel_display (context->splash, display);
}

int
main (int argc, char **argv)
{
        context_t context = { 0 };
        ply_device_manager_t *manager;
        ply_buffer_t *buffer = ply_buffer_new ();
        ply_event_loop_t *loop = ply_event_loop_get_default ();

        CHECK (argc == 3);
        context.splash = ply_boot_splash_new (argv[1], argv[2], buffer);
        CHECK (ply_boot_splash_load (context.splash));
        ply_boot_splash_attach_to_event_loop (context.splash, loop);
        manager = ply_device_manager_new ("/dev/null", PLY_DEVICE_MANAGER_FLAGS_IGNORE_UDEV);
        manager->keyboard_added_handler = (ply_keyboard_added_handler_t) keyboard_added;
        manager->keyboard_removed_handler = (ply_keyboard_removed_handler_t) keyboard_removed;
        manager->pixel_display_added_handler = (ply_pixel_display_added_handler_t) pixel_added;
        manager->pixel_display_removed_handler = (ply_pixel_display_removed_handler_t) pixel_removed;
        manager->event_handler_data = &context;
        CHECK (create_devices_for_terminal_and_renderer_type (manager, NULL, NULL, PLY_RENDERER_TYPE_X11));
        CHECK (context.keyboards_added == 1);
        CHECK (ply_boot_splash_show (context.splash, PLY_BOOT_SPLASH_MODE_BOOT_UP));

        /* The device-removal path used by udev, before hide/quit. A static
         * no-display start falls back to details and cannot exercise this.
         */
        free_renderers (manager);
        CHECK (ply_list_get_length (manager->keyboards) == 0);
        CHECK (ply_list_get_length (manager->pixel_displays) == 0);
        puts ("renderer removed; hiding the splash");
        fflush (stdout);
        ply_boot_splash_hide (context.splash);
        CHECK (context.keyboards_removed == 1);
        ply_boot_splash_free (context.splash);
        context.splash = NULL;
        ply_device_manager_free (manager);
        ply_buffer_free (buffer);
        puts ("renderer removal and splash hide passed");
        return EXIT_SUCCESS;
}
