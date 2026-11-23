CREATE TABLE `audit_events` (
	`id` text NOT NULL,
	`owner` text NOT NULL,
	`at` integer NOT NULL,
	`action` text NOT NULL,
	`result` text NOT NULL,
	`resource` text NOT NULL,
	`correlation` text NOT NULL,
	`version` integer NOT NULL,
	PRIMARY KEY(`owner`, `id`)
);
--> statement-breakpoint
CREATE INDEX `audit_owner_time` ON `audit_events` (`owner`,`at`,`id`);